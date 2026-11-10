#define _POSIX_C_SOURCE 200809L
#include <vulkan/vulkan_core.h>
#include <errno.h>
#include <fcntl.h>
#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

// A bounded, fixed float32 recurrence. No imported shaders or CPU fallback.
// Vulkan 1.0 synchronization, HOST_COHERENT staging and explicit device copies.
#define LIMIT (4u*1024u*1024u)
#define CK(call) do { VkResult r=(call); if(r!=VK_SUCCESS) { \
    fprintf(stderr,"%s: Vulkan result %d\n",#call,r); exit(1); } } while(0)
typedef struct { uint32_t count, first, steps; float gain, offset; } Params;
_Static_assert(sizeof(float)==4 && FLT_MANT_DIG==24 && FLT_RADIX==2,"IEEE float32 required");
_Static_assert(sizeof(Params)==20,"Shader push-constant layout differs");
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "Binary float32 files require a little-endian host"
#endif
typedef struct { VkBuffer buffer; VkDeviceMemory memory; void *mapped; uint32_t type; } Buffer;
static VkInstance instance;
static VkDevice device;
static VkQueue queue;
static VkCommandPool pool;
static VkCommandBuffer command;
static VkFence fence;
static VkPhysicalDeviceMemoryProperties memories;
static VkPipeline pipeline;
static VkPipelineLayout layout;
static VkDescriptorSet descriptor;
static VkDescriptorSetLayout dlayout;
static VkDescriptorPool dpool;
static Buffer staging, data;
static char gpu_name[VK_MAX_PHYSICAL_DEVICE_NAME_SIZE];

static double clock_seconds(void) {
    struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t)) exit(1);
    return t.tv_sec+t.tv_nsec*1e-9;
}
static void quoted(const char *s) {
    putchar('"'); for(;*s;s++) { unsigned char c=(unsigned char)*s;
        if(c=='"'||c=='\\') {putchar('\\');putchar(c);}
        else if(c<32) printf("\\u%04x",c); else putchar(c);
    } putchar('"');
}
static unsigned number(const char *s,unsigned low,unsigned high) {
    char *end; errno=0; unsigned long n=strtoul(s,&end,10);
    if(!*s || *end || errno || n<low || n>high) {
        fputs("Integer outside supported bound\n",stderr); exit(2);
    } return (unsigned)n;
}
static float coefficient(const char *s) {
    char *end; errno=0; float f=strtof(s,&end);
    if(!*s || *end || errno || !isfinite(f) || fabsf(f)>1.0f) {
        fputs("Coefficient must be finite and within [-1,1]\n",stderr);exit(2);
    } return f;
}
static Buffer buffer(VkDeviceSize size,VkBufferUsageFlags usage,VkMemoryPropertyFlags want) {
    Buffer out={0};
    VkBufferCreateInfo b={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=size,
        .usage=usage,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    CK(vkCreateBuffer(device,&b,NULL,&out.buffer));
    VkMemoryRequirements req; vkGetBufferMemoryRequirements(device,out.buffer,&req);
    uint32_t type=UINT32_MAX;
    for(uint32_t i=0;i<memories.memoryTypeCount;i++)
        if((req.memoryTypeBits&(1u<<i)) && (memories.memoryTypes[i].propertyFlags&want)==want) {type=i;break;}
    if(type==UINT32_MAX) {fputs("Required GPU memory type unavailable; no fallback\n",stderr);exit(1);}
    out.type=type;
    VkMemoryAllocateInfo a={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize=req.size,.memoryTypeIndex=type};
    CK(vkAllocateMemory(device,&a,NULL,&out.memory));
    CK(vkBindBufferMemory(device,out.buffer,out.memory,0));
    if(want&VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)
        CK(vkMapMemory(device,out.memory,0,size,0,&out.mapped));
    return out;
}
static void barrier(VkPipelineStageFlags src,VkAccessFlags reads,
                    VkPipelineStageFlags dst,VkAccessFlags writes) {
    VkMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,
        .srcAccessMask=reads,.dstAccessMask=writes};
    vkCmdPipelineBarrier(command,src,dst,0,1,&b,0,NULL,0,NULL);
}
static void begin(void) {
    CK(vkResetCommandPool(device,pool,0));
    VkCommandBufferBeginInfo b={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        .flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    CK(vkBeginCommandBuffer(command,&b));
}
static void finish(void) {
    CK(vkEndCommandBuffer(command));
    VkSubmitInfo s={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,
        .commandBufferCount=1,.pCommandBuffers=&command};
    CK(vkQueueSubmit(queue,1,&s,fence));
    // Stop on a 5 second fence timeout; never submit another lane after failure.
    CK(vkWaitForFences(device,1,&fence,VK_TRUE,5000000000ull));
    CK(vkResetFences(device,1,&fence));
}
static void upload(size_t bytes) {
    VkBufferCopy c={.size=bytes};
    vkCmdCopyBuffer(command,staging.buffer,data.buffer,1,&c);
    barrier(VK_PIPELINE_STAGE_TRANSFER_BIT,VK_ACCESS_TRANSFER_WRITE_BIT,
        VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT);
}
static void download(size_t bytes) {
    barrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_ACCESS_SHADER_WRITE_BIT,
        VK_PIPELINE_STAGE_TRANSFER_BIT,VK_ACCESS_TRANSFER_READ_BIT);
    VkBufferCopy c={.size=bytes};
    vkCmdCopyBuffer(command,data.buffer,staging.buffer,1,&c);
    barrier(VK_PIPELINE_STAGE_TRANSFER_BIT,VK_ACCESS_TRANSFER_WRITE_BIT,
        VK_PIPELINE_STAGE_HOST_BIT,VK_ACCESS_HOST_READ_BIT);
}
static void dispatch(Params p) {
    vkCmdBindPipeline(command,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);
    vkCmdBindDescriptorSets(command,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&descriptor,0,NULL);
    vkCmdPushConstants(command,layout,VK_SHADER_STAGE_COMPUTE_BIT,0,sizeof(p),&p);
    vkCmdDispatch(command,(p.count+255)/256,1,1);
}
static void setup(const char *shader,unsigned n,int cached) {
    VkApplicationInfo a={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName="JUPI finite GPU pipeline",.apiVersion=VK_API_VERSION_1_0};
    VkInstanceCreateInfo ic={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&a};
    CK(vkCreateInstance(&ic,NULL,&instance));
    VkPhysicalDevice physical=VK_NULL_HANDLE; uint32_t count=0;
    CK(vkEnumeratePhysicalDevices(instance,&count,NULL));
    if(count<1 || count>32) {fputs("Device count bound\n",stderr);exit(1);}
    VkPhysicalDevice choices[32]; CK(vkEnumeratePhysicalDevices(instance,&count,choices));
    uint32_t family=UINT32_MAX;
    for(uint32_t i=0;i<count && !physical;i++) {
        VkPhysicalDeviceProperties prop; vkGetPhysicalDeviceProperties(choices[i],&prop);
        // Require the actual AMD GPU, not llvmpipe/lavapipe or an arbitrary device.
        if(prop.vendorID!=0x1002 || (prop.deviceType!=VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU &&
            prop.deviceType!=VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU)) continue;
        uint32_t nf=0; vkGetPhysicalDeviceQueueFamilyProperties(choices[i],&nf,NULL);
        if(!nf || nf>32) continue;
        VkQueueFamilyProperties q[32];vkGetPhysicalDeviceQueueFamilyProperties(choices[i],&nf,q);
        for(uint32_t j=0;j<nf;j++) if(q[j].queueCount && (q[j].queueFlags&VK_QUEUE_COMPUTE_BIT)) {
            physical=choices[i];family=j;snprintf(gpu_name,sizeof(gpu_name),"%s",prop.deviceName);break;
        }
    }
    if(!physical) {fputs("AMD GPU unavailable; CPU substitution disabled\n",stderr);exit(1);}
    float priority=0.25f;
    VkDeviceQueueCreateInfo qc={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
    VkDeviceCreateInfo dc={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount=1,.pQueueCreateInfos=&qc};
    CK(vkCreateDevice(physical,&dc,NULL,&device));vkGetDeviceQueue(device,family,0,&queue);
    vkGetPhysicalDeviceMemoryProperties(physical,&memories);
    VkCommandPoolCreateInfo pc={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .queueFamilyIndex=family};CK(vkCreateCommandPool(device,&pc,NULL,&pool));
    VkCommandBufferAllocateInfo ca={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    CK(vkAllocateCommandBuffers(device,&ca,&command));
    VkFenceCreateInfo fc={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};CK(vkCreateFence(device,&fc,NULL,&fence));
    size_t bytes=(size_t)n*sizeof(float);
    staging=buffer(bytes,VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT,
        VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT|
        (cached?VK_MEMORY_PROPERTY_HOST_CACHED_BIT:0));
    data=buffer(bytes,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|
        VK_BUFFER_USAGE_TRANSFER_DST_BIT,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT);
    VkDescriptorSetLayoutBinding binding={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
        .descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo dl={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
        .bindingCount=1,.pBindings=&binding};CK(vkCreateDescriptorSetLayout(device,&dl,NULL,&dlayout));
    VkPushConstantRange push={.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT,.size=sizeof(Params)};
    VkPipelineLayoutCreateInfo pl={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .setLayoutCount=1,.pSetLayouts=&dlayout,.pushConstantRangeCount=1,.pPushConstantRanges=&push};
    CK(vkCreatePipelineLayout(device,&pl,NULL,&layout));
    FILE *f=fopen(shader,"rb");if(!f) {perror("shader");exit(1);}
    if(fseek(f,0,SEEK_END)) exit(1);
    long length=ftell(f);rewind(f);
    if(length<20 || length>1048576 || length%4) {fputs("Shader size bound\n",stderr);exit(1);}
    uint32_t *code=malloc((size_t)length);if(!code) exit(1);
    if(fread(code,1,(size_t)length,f)!=(size_t)length || fclose(f) || code[0]!=0x07230203u) exit(1);
    VkShaderModuleCreateInfo sm={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize=(size_t)length,.pCode=code};VkShaderModule module;
    CK(vkCreateShaderModule(device,&sm,NULL,&module));free(code);
    VkComputePipelineCreateInfo cp={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=module,.pName="main"},.layout=layout};
    CK(vkCreateComputePipelines(device,VK_NULL_HANDLE,1,&cp,NULL,&pipeline));
    vkDestroyShaderModule(device,module,NULL);
    VkDescriptorPoolSize ps={.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1};
    VkDescriptorPoolCreateInfo dp={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .maxSets=1,.poolSizeCount=1,.pPoolSizes=&ps};CK(vkCreateDescriptorPool(device,&dp,NULL,&dpool));
    VkDescriptorSetAllocateInfo da={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
        .descriptorPool=dpool,.descriptorSetCount=1,.pSetLayouts=&dlayout};
    CK(vkAllocateDescriptorSets(device,&da,&descriptor));
    VkDescriptorBufferInfo bi={.buffer=data.buffer,.range=bytes};
    VkWriteDescriptorSet write={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=descriptor,
        .dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&bi};
    vkUpdateDescriptorSets(device,1,&write,0,NULL);
}
static void cleanup(void) {
    vkUnmapMemory(device,staging.memory);
    vkDestroyBuffer(device,staging.buffer,NULL);vkFreeMemory(device,staging.memory,NULL);
    vkDestroyBuffer(device,data.buffer,NULL);vkFreeMemory(device,data.memory,NULL);
    vkDestroyDescriptorPool(device,dpool,NULL);vkDestroyPipeline(device,pipeline,NULL);
    vkDestroyPipelineLayout(device,layout,NULL);vkDestroyDescriptorSetLayout(device,dlayout,NULL);
    vkDestroyFence(device,fence,NULL);vkDestroyCommandPool(device,pool,NULL);
    vkDestroyDevice(device,NULL);vkDestroyInstance(instance,NULL);
}
static void cpu(float *out,const float *in,Params p) {
    memcpy(out,in,(size_t)p.count*sizeof(float));
    for(unsigned s=0;s<p.steps;s++) {
        float bias=p.offset*(float)(s+1);
        for(unsigned i=0;i<p.count;i++) out[i]=out[i]*p.gain+bias;
    }
}
static void cpu_fused(float *out,const float *in,Params p,int threads) {
    // Specialize the common eight-stage case so the compiler can vectorize
    // across samples; retain each float32 operation and its original order.
    if(p.steps==8) {
        #pragma omp parallel for simd num_threads(threads) if(threads>1)
        for(unsigned i=0;i<p.count;i++) {
            float x=in[i];
            #pragma GCC unroll 8
            for(unsigned s=0;s<8;s++) x=x*p.gain+p.offset*(float)(s+1);
            out[i]=x;
        }
        return;
    }
    #pragma omp parallel for simd num_threads(threads) if(threads>1)
    for(unsigned i=0;i<p.count;i++) {
        float x=in[i];
        for(unsigned s=0;s<p.steps;s++) {
            float bias=p.offset*(float)(s+1);
            x=x*p.gain+bias;
        }
        out[i]=x;
    }
}
static void cpu_parallel(float *out,const float *in,Params p) {
    #pragma omp parallel num_threads(4)
    {
        #pragma omp for simd
        for(unsigned i=0;i<p.count;i++) out[i]=in[i];
        for(unsigned s=0;s<p.steps;s++) {
            float bias=p.offset*(float)(s+1);
            #pragma omp for simd
            for(unsigned i=0;i<p.count;i++) out[i]=out[i]*p.gain+bias;
        }
    }
}
static void gpu(float *out,const float *in,Params p,int mode) {
    size_t bytes=(size_t)p.count*sizeof(float);
    memcpy(staging.mapped,in,bytes);
    if(mode==0) {
        for(unsigned s=0;s<p.steps;s++) {
            begin();upload(bytes);Params stage=p;stage.first=s;stage.steps=1;
            dispatch(stage);download(bytes);finish();
            // This intentionally models the round trip through an application array.
            memcpy(out,staging.mapped,bytes);
            if(s+1<p.steps) memcpy(staging.mapped,out,bytes);
        }
    } else {
        begin();upload(bytes);
        if(mode==1) for(unsigned s=0;s<p.steps;s++) {
            if(s) barrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_ACCESS_SHADER_WRITE_BIT,
                VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT);
            Params stage=p;stage.first=s;stage.steps=1;dispatch(stage);
        } else dispatch(p);
        download(bytes);finish();memcpy(out,staging.mapped,bytes);
    }
}
static unsigned validate(const float *a,const float *b,unsigned n,float *maximum) {
    unsigned errors=0;*maximum=0;
    for(unsigned i=0;i<n;i++) {
        if(!isfinite(a[i]) || !isfinite(b[i]) || memcmp(a+i,b+i,sizeof(float))) errors++;
        float d=fabsf(a[i]-b[i]);if(d>*maximum)*maximum=d;
    }return errors;
}
int main(int argc,char **argv) {
    // bench SHADER SAMPLES STEPS REPS POLICY | apply SHADER IN OUT STEPS GAIN OFFSET MODE POLICY
    if(argc<2 || (strcmp(argv[1],"bench") && strcmp(argv[1],"apply"))) return 2;
    int bench=!strcmp(argv[1],"bench");
    if((bench && argc!=7) || (!bench && argc!=10)) return 2;
    const char *policy=argv[bench?6:9];
    if(strcmp(policy,"cached") && strcmp(policy,"first-coherent")) return 2;
    Params p={.first=0,.gain=0.75f,.offset=0.0001f};unsigned reps=1;
    FILE *input=NULL;
    if(bench) {p.count=number(argv[3],1,LIMIT);p.steps=number(argv[4],1,32);reps=number(argv[5],1,15);}
    else {
        p.steps=number(argv[5],1,32);p.gain=coefficient(argv[6]);p.offset=coefficient(argv[7]);
        input=fopen(argv[3],"rb");if(!input) return 2;
        if(fseek(input,0,SEEK_END)) return 2;
        long bytes=ftell(input);rewind(input);
        if(bytes<4 || bytes>(long)LIMIT*4 || bytes%4) return 2;
        p.count=(unsigned)bytes/4;
    }
    size_t bytes=(size_t)p.count*sizeof(float);
    float *in=malloc(bytes),*out=malloc(bytes),*expected=malloc(bytes);
    if(!in || !out || !expected) return 1;
    if(bench) for(unsigned i=0;i<p.count;i++)
        in[i]=(float)((i*1664525u+1013904223u)&65535u)/65536.0f-0.5f;
    else {
        if(fread(in,1,bytes,input)!=bytes || fgetc(input)!=EOF || fclose(input)) return 2;
        for(unsigned i=0;i<p.count;i++) if(!isfinite(in[i]) || fabsf(in[i])>1e6f) return 2;
    }
    double started=clock_seconds();setup(argv[2],p.count,!strcmp(policy,"cached"));double setup_s=clock_seconds()-started;
    cpu(expected,in,p);
    const char *names[]={"roundtrip","resident","fused","cpu","cpu-fused-1","cpu-fused-4","cpu-staged-4"};
    printf("{\"schema\":\"jupi.gpu.pipeline.v1\",\"device\":");quoted(gpu_name);
    printf(",\"staging_policy\":\"%s\",\"staging_type\":%u,\"staging_flags\":%u",
        policy,staging.type,memories.memoryTypes[staging.type].propertyFlags);
    printf(",\"samples\":%u,\"steps\":%u,\"gain_f32\":%.9g,\"offset_f32\":%.9g,\"setup_seconds\":%.9g,\"lanes\":[",
        p.count,p.steps,p.gain,p.offset,setup_s);
    int mode_first=0,mode_last=6;
    if(!bench) {
        mode_first=-1;for(int m=0;m<3;m++) if(!strcmp(argv[8],names[m])) mode_first=m;
        if(mode_first<0) return 2;
        mode_last=mode_first;
    }
    unsigned failures=0;
    for(int mode=mode_first;mode<=mode_last;mode++) {
        if(mode!=mode_first) putchar(',');
        if(mode<3) gpu(out,in,p,mode);
        else if(mode==3) cpu(out,in,p);
        else if(mode<6) cpu_fused(out,in,p,mode==4?1:4);
        else cpu_parallel(out,in,p); // untimed warmup
        float maximum;unsigned errors=validate(out,expected,p.count,&maximum);
        printf("{\"mode\":\"%s\",\"seconds\":[",names[mode]);
        for(unsigned rep=0;rep<reps;rep++) {
            double t=clock_seconds();
            if(mode<3) gpu(out,in,p,mode);
            else if(mode==3) cpu(out,in,p);
            else if(mode<6) cpu_fused(out,in,p,mode==4?1:4);
            else cpu_parallel(out,in,p);
            double elapsed=clock_seconds()-t;
            unsigned e=validate(out,expected,p.count,&maximum);errors+=e;
            if(rep) putchar(',');
            printf("%.9g",elapsed);
        }
        printf("],\"mismatches\":%u,\"max_absolute_error_last\":%.9g}",errors,maximum);
        failures+=errors;
    }
    puts("],\"timing_scope\":\"Host monotonic wall time including command recording, upload, GPU work, download and host copies; setup and full validation excluded\",\"verification\":\"Every output bitwise compared with separate float32 CPU recurrence on every repetition\"}");
    if(!bench && !failures) {
        int fd=open(argv[4],O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0) return 1;
        FILE *f=fdopen(fd,"wb");if(!f) {close(fd);return 1;}
        if(fwrite(out,1,bytes,f)!=bytes || fflush(f) || fsync(fd) || fclose(f)) return 1;
    }
    cleanup();free(in);free(out);free(expected);return failures?1:0;
}
