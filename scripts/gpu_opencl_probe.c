#define CL_TARGET_OPENCL_VERSION 120
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>

#define CHECK(call) do { cl_int code = (call); if (code != CL_SUCCESS) { \
    fprintf(stderr, "%s failed: %d\n", #call, code); return 1; } } while (0)

int main(void) {
    cl_platform_id platforms[16]; cl_uint count = 0;
    cl_device_id device = NULL;
    CHECK(clGetPlatformIDs(16, platforms, &count));
    for (cl_uint i = 0; i < count && i < 16; ++i) {
        if (clGetDeviceIDs(platforms[i], CL_DEVICE_TYPE_GPU, 1, &device, NULL) == CL_SUCCESS)
            break;
        device = NULL;
    }
    if (!device) { fputs("No OpenCL GPU device\n", stderr); return 1; }
    char name[512] = {0};
    CHECK(clGetDeviceInfo(device, CL_DEVICE_NAME, sizeof(name), name, NULL));
    cl_int error;
    cl_context context = clCreateContext(NULL, 1, &device, NULL, NULL, &error);
    CHECK(error);
    cl_command_queue queue = clCreateCommandQueue(context, device, 0, &error);
    CHECK(error);
    const char *source = "__kernel void add(__global const float *a, __global const float *b, __global float *c) {size_t i=get_global_id(0); c[i]=a[i]+b[i];}";
    cl_program program = clCreateProgramWithSource(context, 1, &source, NULL, &error);
    CHECK(error);
    error = clBuildProgram(program, 1, &device, "", NULL, NULL);
    if (error != CL_SUCCESS) {
        char log[16384] = {0};
        clGetProgramBuildInfo(program, device, CL_PROGRAM_BUILD_LOG, sizeof(log), log, NULL);
        fprintf(stderr, "OpenCL build failed: %d\n%s\n", error, log); return 1;
    }
    enum { N = 1024 }; float a[N], b[N], c[N];
    for (int i = 0; i < N; ++i) { a[i] = (float)i; b[i] = (float)(2*i); }
    cl_mem ma = clCreateBuffer(context, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(a), a, &error); CHECK(error);
    cl_mem mb = clCreateBuffer(context, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, sizeof(b), b, &error); CHECK(error);
    cl_mem mc = clCreateBuffer(context, CL_MEM_WRITE_ONLY, sizeof(c), NULL, &error); CHECK(error);
    cl_kernel kernel = clCreateKernel(program, "add", &error); CHECK(error);
    CHECK(clSetKernelArg(kernel, 0, sizeof(ma), &ma));
    CHECK(clSetKernelArg(kernel, 1, sizeof(mb), &mb));
    CHECK(clSetKernelArg(kernel, 2, sizeof(mc), &mc));
    size_t global = N;
    CHECK(clEnqueueNDRangeKernel(queue, kernel, 1, NULL, &global, NULL, 0, NULL, NULL));
    CHECK(clEnqueueReadBuffer(queue, mc, CL_TRUE, 0, sizeof(c), c, 0, NULL, NULL));
    int mismatches = 0;
    for (int i = 0; i < N; ++i) if (c[i] != (float)(3*i)) ++mismatches;
    printf("OpenCL GPU: %s\nvector_add_elements=%d mismatches=%d\n", name, N, mismatches);
    clReleaseKernel(kernel); clReleaseMemObject(ma); clReleaseMemObject(mb); clReleaseMemObject(mc);
    clReleaseProgram(program); clReleaseCommandQueue(queue); clReleaseContext(context);
    return mismatches ? 1 : 0;
}
