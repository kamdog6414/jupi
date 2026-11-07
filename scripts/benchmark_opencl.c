#define _POSIX_C_SOURCE 200809L
#define CL_TARGET_OPENCL_VERSION 110
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define CHECK(x) do { cl_int e=(x); if(e!=CL_SUCCESS) {fprintf(stderr,"%s: %d\n",#x,e); return 1;} } while(0)
static double now(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(void) {
    const size_t n=1048576,bytes=n*sizeof(float);
    float *a=malloc(bytes),*b=malloc(bytes),*c=malloc(bytes);
    if(!a||!b||!c)return 1;
    for(size_t i=0;i<n;i++){a[i]=(float)(i%1024);b[i]=2*a[i];}
    cl_platform_id platforms[16];cl_uint count=0;cl_device_id device=NULL;cl_int error;
    CHECK(clGetPlatformIDs(16,platforms,&count));
    for(cl_uint i=0;i<count&&i<16;i++) {if(clGetDeviceIDs(platforms[i],CL_DEVICE_TYPE_GPU,1,&device,NULL)==CL_SUCCESS)break;device=NULL;}
    if(!device)return 1;
    cl_context ctx=clCreateContext(NULL,1,&device,NULL,NULL,&error);CHECK(error);
    cl_command_queue q=clCreateCommandQueue(ctx,device,0,&error);CHECK(error);
    const char *src="__kernel void add(__global const float *a,__global const float *b,__global float *c){size_t i=get_global_id(0);c[i]=a[i]+b[i];}";
    cl_program p=clCreateProgramWithSource(ctx,1,&src,NULL,&error);CHECK(error);
    CHECK(clBuildProgram(p,1,&device,"",NULL,NULL));
    cl_kernel k=clCreateKernel(p,"add",&error);CHECK(error);
    cl_mem ma=clCreateBuffer(ctx,CL_MEM_READ_ONLY|CL_MEM_COPY_HOST_PTR,bytes,a,&error);CHECK(error);
    cl_mem mb=clCreateBuffer(ctx,CL_MEM_READ_ONLY|CL_MEM_COPY_HOST_PTR,bytes,b,&error);CHECK(error);
    cl_mem mc=clCreateBuffer(ctx,CL_MEM_WRITE_ONLY,bytes,NULL,&error);CHECK(error);
    CHECK(clSetKernelArg(k,0,sizeof(ma),&ma));CHECK(clSetKernelArg(k,1,sizeof(mb),&mb));CHECK(clSetKernelArg(k,2,sizeof(mc),&mc));
    for(int i=0;i<3;i++){CHECK(clEnqueueNDRangeKernel(q,k,1,NULL,&n,NULL,0,NULL,NULL));CHECK(clFinish(q));}
    double start=now(),elapsed;unsigned runs=0;
    do {CHECK(clEnqueueNDRangeKernel(q,k,1,NULL,&n,NULL,0,NULL,NULL));CHECK(clFinish(q));runs++;elapsed=now()-start;}while(elapsed<3 && runs<100000);
    CHECK(clEnqueueReadBuffer(q,mc,CL_TRUE,0,bytes,c,0,NULL,NULL));
    unsigned bad=0;for(size_t i=0;i<n;i++)if(c[i]!=(float)(3*(i%1024)))bad++;
    printf("{\"elements\":%zu,\"iterations\":%u,\"seconds\":%.9f,\"nominal_GB_s\":%.6f,\"mismatches\":%u,\"timing\":\"host monotonic enqueue plus clFinish; three nominal float transfers\"}\n",n,runs,elapsed,3.0*bytes*runs/elapsed/1e9,bad);
    clReleaseMemObject(ma);clReleaseMemObject(mb);clReleaseMemObject(mc);clReleaseKernel(k);clReleaseProgram(p);clReleaseCommandQueue(q);clReleaseContext(ctx);free(a);free(b);free(c);
    return bad?1:0;
}
