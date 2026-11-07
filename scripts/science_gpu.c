#define _POSIX_C_SOURCE 200809L
#define CL_TARGET_OPENCL_VERSION 110
#include <CL/cl.h>
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "The recorded binary format requires a little-endian host"
#endif
#define CHECK(call) do { error=(call); if(error!=CL_SUCCESS) { fprintf(stderr,"OpenCL %s: %d\n",#call,error); goto done; } } while(0)

static void json_string(const char *s) {
    putchar('"');
    for (;*s;s++) {
        unsigned char c=(unsigned char)*s;
        if(c=='"'||c=='\\') {putchar('\\');putchar(c);}
        else if(c<32) printf("\\u%04x",c);
        else putchar(c);
    }
    putchar('"');
}

int main(int argc,char **argv) {
    if(argc!=5) {fputs("Usage: science-gpu INPUT.f32 OUTPUT.f32 SAMPLES GAIN\n",stderr);return 2;}
    char *end=NULL;errno=0;
    unsigned long n=strtoul(argv[3],&end,10);
    if(errno||*end||n<1||n>65536) {fputs("Sample bound\n",stderr);return 2;}
    errno=0;float gain=strtof(argv[4],&end);
    if(errno||*end||!isfinite(gain)) {fputs("Gain bound\n",stderr);return 2;}
    size_t bytes=2*n*sizeof(float);
    float *input=malloc(bytes),*output=malloc(bytes);
    if(!input||!output) {free(input);free(output);return 1;}
    FILE *file=fopen(argv[1],"rb");
    if(!file||fread(input,1,bytes,file)!=bytes||fgetc(file)!=EOF) {if(file)fclose(file);free(input);free(output);return 1;}
    fclose(file);
    for(size_t i=0;i<2*n;i++) if(!isfinite(input[i])) {free(input);free(output);return 2;}
    int status=1;cl_int error=CL_SUCCESS;
    cl_context context=NULL;cl_command_queue queue=NULL;cl_program program=NULL;
    cl_kernel kernel=NULL;cl_mem in=NULL,out=NULL;cl_event event=NULL;
    cl_platform_id platforms[16];cl_uint count=0;cl_device_id device=NULL;
    CHECK(clGetPlatformIDs(16,platforms,&count));
    for(cl_uint i=0;i<count&&i<16;i++) {
        if(clGetDeviceIDs(platforms[i],CL_DEVICE_TYPE_GPU,1,&device,NULL)==CL_SUCCESS)break;
        device=NULL;
    }
    if(!device) {fputs("No OpenCL GPU; CPU substitution is disabled\n",stderr);goto done;}
    char name[512]={0},driver[512]={0},version[512]={0};
    CHECK(clGetDeviceInfo(device,CL_DEVICE_NAME,sizeof(name),name,NULL));
    CHECK(clGetDeviceInfo(device,CL_DRIVER_VERSION,sizeof(driver),driver,NULL));
    CHECK(clGetDeviceInfo(device,CL_DEVICE_VERSION,sizeof(version),version,NULL));
    context=clCreateContext(NULL,1,&device,NULL,NULL,&error);CHECK(error);
    queue=clCreateCommandQueue(context,device,CL_QUEUE_PROFILING_ENABLE,&error);CHECK(error);
    const char *source="__kernel void calibrate(__global const float2 *a,__global float2 *b,float gain){size_t i=get_global_id(0);float2 z=a[i];float p=gain*z.x;b[i]=(float2)(p,z.y-p);}";
    program=clCreateProgramWithSource(context,1,&source,NULL,&error);CHECK(error);
    error=clBuildProgram(program,1,&device,"",NULL,NULL);
    if(error!=CL_SUCCESS) {char log[8192]={0};clGetProgramBuildInfo(program,device,CL_PROGRAM_BUILD_LOG,sizeof(log),log,NULL);fprintf(stderr,"Build error %d: %s\n",error,log);goto done;}
    in=clCreateBuffer(context,CL_MEM_READ_ONLY|CL_MEM_COPY_HOST_PTR,bytes,input,&error);CHECK(error);
    out=clCreateBuffer(context,CL_MEM_WRITE_ONLY,bytes,NULL,&error);CHECK(error);
    kernel=clCreateKernel(program,"calibrate",&error);CHECK(error);
    CHECK(clSetKernelArg(kernel,0,sizeof(in),&in));CHECK(clSetKernelArg(kernel,1,sizeof(out),&out));
    CHECK(clSetKernelArg(kernel,2,sizeof(gain),&gain));
    size_t global=n;
    CHECK(clEnqueueNDRangeKernel(queue,kernel,1,NULL,&global,NULL,0,NULL,&event));
    CHECK(clEnqueueReadBuffer(queue,out,CL_TRUE,0,bytes,output,0,NULL,NULL));
    for(size_t i=0;i<2*n;i++) if(!isfinite(output[i])) {fputs("Non-finite GPU result\n",stderr);goto done;}
    int fd=open(argv[2],O_WRONLY|O_CREAT|O_EXCL,0600);
    if(fd<0) {perror("Output creation");goto done;}
    file=fdopen(fd,"wb");
    if(!file) {close(fd);goto done;}
    if(fwrite(output,1,bytes,file)!=bytes||fflush(file)||fsync(fd)) {fclose(file);goto done;}
    if(fclose(file)) goto done;
    cl_ulong start=0,finish=0;
    int timing=(clGetEventProfilingInfo(event,CL_PROFILING_COMMAND_START,sizeof(start),&start,NULL)==CL_SUCCESS && clGetEventProfilingInfo(event,CL_PROFILING_COMMAND_END,sizeof(finish),&finish,NULL)==CL_SUCCESS && finish>=start);
    printf("{\"backend\":\"OpenCL GPU\",\"samples\":%lu,\"device\":",n);json_string(name);
    printf(",\"driver\":");json_string(driver);printf(",\"opencl_version\":");json_string(version);
    printf(",\"kernel_time_ns\":");if(timing)printf("%llu",(unsigned long long)(finish-start));else printf("null");
    printf(",\"gain_float32\":%.9g}\n",gain);status=0;
done:
    if(event)clReleaseEvent(event);
    if(kernel)clReleaseKernel(kernel);
    if(in)clReleaseMemObject(in);
    if(out)clReleaseMemObject(out);
    if(program)clReleaseProgram(program);
    if(queue)clReleaseCommandQueue(queue);
    if(context)clReleaseContext(context);
    free(input);free(output);return status;
}
