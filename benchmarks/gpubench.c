#define _POSIX_C_SOURCE 199309L
#include <CL/cl.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static const char* SRC =
"__kernel void fma32(__global float* out, int K){ float8 a=(float8)(1.0001f); float8 b=(float8)(0.9999f); float8 c=(float8)(0.5f); for(int i=0;i<K;i++){ a=a*b+c; b=b*a+c; } if(get_global_id(0)==0){ out[0]=a.s0+a.s1+b.s2; } }"
"__kernel void fma64(__global double* out, int K){ double2 a=(double2)(1.0001); double2 b=(double2)(0.9999); double2 c=(double2)(0.5); for(int i=0;i<K;i++){ a=a*b+c; b=b*a+c; } if(get_global_id(0)==0){ out[0]=a.x+a.y+b.x; } }"
"__kernel void copyk(__global float* dst, __global const float* src){ size_t i=get_global_id(0); dst[i]=src[i]; }";
int main(void){
 cl_platform_id pf; cl_device_id dev; cl_int e;
 e=clGetPlatformIDs(1,&pf,NULL); if(e){printf("ERR platform %d\n",e);return 1;}
 e=clGetDeviceIDs(pf,CL_DEVICE_TYPE_GPU,1,&dev,NULL); if(e){printf("ERR device %d\n",e);return 1;}
 char name[256]; clGetDeviceInfo(dev,CL_DEVICE_NAME,sizeof(name),name,NULL); printf("DEVICE %s\n",name);
 cl_context ctx=clCreateContext(NULL,1,&dev,NULL,NULL,&e);
 cl_command_queue q=clCreateCommandQueue(ctx,dev,0,&e);
 cl_program pr=clCreateProgramWithSource(ctx,1,&SRC,NULL,&e);
 e=clBuildProgram(pr,1,&dev,NULL,NULL,NULL);
 if(e){ char log[2048]; size_t n; clGetProgramBuildInfo(pr,dev,CL_PROGRAM_BUILD_LOG,sizeof(log),log,&n); printf("ERR build %d %s\n",e,log); return 1; }
 cl_mem out=clCreateBuffer(ctx,CL_MEM_WRITE_ONLY,64,NULL,&e);
 size_t wg=256;
 { cl_kernel k=clCreateKernel(pr,"fma32",&e); int K=4000; size_t g=294912;
   clSetKernelArg(k,0,sizeof(cl_mem),&out); clSetKernelArg(k,1,sizeof(int),&K);
   double t0=now(); clEnqueueNDRangeKernel(q,k,1,NULL,&g,&wg,0,NULL,NULL); clFinish(q); double dt=now()-t0;
   double gf=294912.0*K*32.0/1e9; printf("FP32 %.1f GFLOPS (%.3f s, %.1f GFLOP)\n", gf/dt, dt, gf); clReleaseKernel(k); }
 { cl_kernel k=clCreateKernel(pr,"fma64",&e); int K=2000; size_t g=147456;
   clSetKernelArg(k,0,sizeof(cl_mem),&out); clSetKernelArg(k,1,sizeof(int),&K);
   double t0=now(); clEnqueueNDRangeKernel(q,k,1,NULL,&g,&wg,0,NULL,NULL); clFinish(q); double dt=now()-t0;
   double gf=147456.0*K*8.0/1e9; printf("FP64 %.1f GFLOPS (%.3f s, %.2f GFLOP)\n", gf/dt, dt, gf); clReleaseKernel(k); }
 { size_t n=67108864; cl_mem a=clCreateBuffer(ctx,CL_MEM_READ_ONLY,n*4,NULL,&e); cl_mem b=clCreateBuffer(ctx,CL_MEM_WRITE_ONLY,n*4,NULL,&e);
   cl_kernel k=clCreateKernel(pr,"copyk",&e); clSetKernelArg(k,0,sizeof(cl_mem),&b); clSetKernelArg(k,1,sizeof(cl_mem),&a);
   double best=1e9; for(int r=0;r<5;r++){ double t0=now(); clEnqueueNDRangeKernel(q,k,1,NULL,&n,&wg,0,NULL,NULL); clFinish(q); double dt=now()-t0; if(dt<best)best=dt; }
   double gb=2.0*n*4/1e9; printf("BW %.1f GB/s (best %.3f s, %.2f GB moved)\n", gb/best, best, gb); clReleaseKernel(k); }
 return 0; }
