/* vkprobe.c — minimal Vulkan compute probe for JUPI (RADV Liverpool).
   Hand-declared Vulkan 1.0 ABI via dlopen (no headers on the box).
   Mirrors gpubench.c (OpenCL) exactly: same FMA chain math, same
   thread counts, same K, same copy size, wall-clock timing.
   FP32: float8 = 2x vec4, 2 chained FMAs per vec4 -> 32 flop/thread/iter
   FP64: double2, 2 chained FMAs -> 8 flop/thread/iter
   Copy: 64M floats read+write, best of 5. FMA runs 3 reps (cold..warm). */
#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <dlfcn.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
typedef int32_t VkResult; typedef uint64_t VkDeviceSize;
typedef void* VkInstance; typedef void* VkPhysicalDevice; typedef void* VkDevice;
typedef void* VkQueue; typedef void* VkCommandBuffer;
typedef uint64_t VkBuffer; typedef uint64_t VkDeviceMemory; typedef uint64_t VkShaderModule;
typedef uint64_t VkDescriptorSetLayout; typedef uint64_t VkPipelineLayout; typedef uint64_t VkPipeline;
typedef uint64_t VkDescriptorPool; typedef uint64_t VkDescriptorSet; typedef uint64_t VkCommandPool; typedef uint64_t VkFence;
typedef struct{uint32_t sType;const void*pNext;const char*pApplicationName;uint32_t applicationVersion;const char*pEngineName;uint32_t engineVersion;uint32_t apiVersion;} VkApplicationInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;const VkApplicationInfo*pApplicationInfo;uint32_t enabledLayerCount;const char*const*ppEnabledLayerNames;uint32_t enabledExtensionCount;const char*const*ppEnabledExtensionNames;} VkInstanceCreateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t queueFamilyIndex;uint32_t queueCount;const float*pQueuePriorities;} VkDeviceQueueCreateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t queueCreateInfoCount;const VkDeviceQueueCreateInfo*pQueueCreateInfos;uint32_t enabledLayerCount;const char*const*ppEnabledLayerNames;uint32_t enabledExtensionCount;const char*const*ppEnabledExtensionNames;const void*pEnabledFeatures;} VkDeviceCreateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;VkDeviceSize size;uint32_t usage;uint32_t sharingMode;uint32_t queueFamilyIndexCount;const uint32_t*pQueueFamilyIndices;} VkBufferCreateInfo;
typedef struct{VkDeviceSize size;VkDeviceSize alignment;uint32_t memoryTypeBits;} VkMemoryRequirements;
typedef struct{uint32_t sType;const void*pNext;VkDeviceSize allocationSize;uint32_t memoryTypeIndex;} VkMemoryAllocateInfo;
typedef struct{uint32_t propertyFlags;uint32_t heapIndex;} VkMemoryType;
typedef struct{VkDeviceSize size;uint32_t flags;uint32_t pad;} VkMemoryHeap;
typedef struct{uint32_t memoryTypeCount;VkMemoryType memoryTypes[32];uint32_t memoryHeapCount;VkMemoryHeap memoryHeaps[16];} VkPhysicalDeviceMemoryProperties;
typedef struct{uint32_t queueFlags;uint32_t queueCount;uint32_t timestampValidBits;uint32_t eW,eH,eD;} VkQueueFamilyProperties;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;size_t codeSize;const uint32_t*pCode;} VkShaderModuleCreateInfo;
typedef struct{uint32_t binding;uint32_t descriptorType;uint32_t descriptorCount;uint32_t stageFlags;const void*pImmutableSamplers;} VkDescriptorSetLayoutBinding;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t bindingCount;const VkDescriptorSetLayoutBinding*pBindings;} VkDescriptorSetLayoutCreateInfo;
typedef struct{uint32_t stageFlags;uint32_t offset;uint32_t size;} VkPushConstantRange;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t setLayoutCount;const VkDescriptorSetLayout*pSetLayouts;uint32_t pushConstantRangeCount;const VkPushConstantRange*pPushConstantRanges;} VkPipelineLayoutCreateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t stage;VkShaderModule module;const char*pName;const void*pSpecializationInfo;} VkPipelineShaderStageCreateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;VkPipelineShaderStageCreateInfo stage;VkPipelineLayout layout;VkPipeline basePipelineHandle;int32_t basePipelineIndex;} VkComputePipelineCreateInfo;
typedef struct{uint32_t type;uint32_t descriptorCount;} VkDescriptorPoolSize;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t maxSets;uint32_t poolSizeCount;const VkDescriptorPoolSize*pPoolSizes;} VkDescriptorPoolCreateInfo;
typedef struct{uint32_t sType;const void*pNext;VkDescriptorPool descriptorPool;uint32_t descriptorSetCount;const VkDescriptorSetLayout*pSetLayouts;} VkDescriptorSetAllocateInfo;
typedef struct{VkBuffer buffer;VkDeviceSize offset;VkDeviceSize range;} VkDescriptorBufferInfo;
typedef struct{uint32_t sType;const void*pNext;VkDescriptorSet dstSet;uint32_t dstBinding;uint32_t dstArrayElement;uint32_t descriptorCount;uint32_t descriptorType;const void*pImageInfo;const VkDescriptorBufferInfo*pBufferInfo;const void*pTexelBufferView;} VkWriteDescriptorSet;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;uint32_t queueFamilyIndex;} VkCommandPoolCreateInfo;
typedef struct{uint32_t sType;const void*pNext;VkCommandPool commandPool;uint32_t level;uint32_t commandBufferCount;} VkCommandBufferAllocateInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;const void*pInheritanceInfo;} VkCommandBufferBeginInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t waitSemaphoreCount;const void*pWaitSemaphores;const uint32_t*pWaitDstStageMask;uint32_t commandBufferCount;const VkCommandBuffer*pCommandBuffers;uint32_t signalSemaphoreCount;const void*pSignalSemaphores;} VkSubmitInfo;
typedef struct{uint32_t sType;const void*pNext;uint32_t flags;} VkFenceCreateInfo;
static VkResult (*pCreateInstance)(const VkInstanceCreateInfo*,const void*,VkInstance*);
static VkResult (*pEnumeratePhysicalDevices)(VkInstance,uint32_t*,VkPhysicalDevice*);
static void (*pGetPhysicalDeviceProperties)(VkPhysicalDevice,void*);
static void (*pGetPhysicalDeviceQueueFamilyProperties)(VkPhysicalDevice,uint32_t*,VkQueueFamilyProperties*);
static VkResult (*pCreateDevice)(VkPhysicalDevice,const VkDeviceCreateInfo*,const void*,VkDevice*);
static void (*pGetDeviceQueue)(VkDevice,uint32_t,uint32_t,VkQueue*);
static VkResult (*pCreateBuffer)(VkDevice,const VkBufferCreateInfo*,const void*,VkBuffer*);
static void (*pGetBufferMemoryRequirements)(VkDevice,VkBuffer,VkMemoryRequirements*);
static void (*pGetPhysicalDeviceMemoryProperties)(VkPhysicalDevice,VkPhysicalDeviceMemoryProperties*);
static VkResult (*pAllocateMemory)(VkDevice,const VkMemoryAllocateInfo*,const void*,VkDeviceMemory*);
static VkResult (*pBindBufferMemory)(VkDevice,VkBuffer,VkDeviceMemory,VkDeviceSize);
static VkResult (*pMapMemory)(VkDevice,VkDeviceMemory,VkDeviceSize,VkDeviceSize,uint32_t,void**);
static void (*pUnmapMemory)(VkDevice,VkDeviceMemory);
static VkResult (*pCreateShaderModule)(VkDevice,const VkShaderModuleCreateInfo*,const void*,VkShaderModule*);
static VkResult (*pCreateDescriptorSetLayout)(VkDevice,const VkDescriptorSetLayoutCreateInfo*,const void*,VkDescriptorSetLayout*);
static VkResult (*pCreatePipelineLayout)(VkDevice,const VkPipelineLayoutCreateInfo*,const void*,VkPipelineLayout*);
static VkResult (*pCreateComputePipelines)(VkDevice,uint64_t,uint32_t,const VkComputePipelineCreateInfo*,const void*,VkPipeline*);
static VkResult (*pCreateDescriptorPool)(VkDevice,const VkDescriptorPoolCreateInfo*,const void*,VkDescriptorPool*);
static VkResult (*pAllocateDescriptorSets)(VkDevice,const VkDescriptorSetAllocateInfo*,VkDescriptorSet*);
static void (*pUpdateDescriptorSets)(VkDevice,uint32_t,const VkWriteDescriptorSet*,uint32_t,const void*);
static VkResult (*pCreateCommandPool)(VkDevice,const VkCommandPoolCreateInfo*,const void*,VkCommandPool*);
static VkResult (*pAllocateCommandBuffers)(VkDevice,const VkCommandBufferAllocateInfo*,VkCommandBuffer*);
static VkResult (*pBeginCommandBuffer)(VkCommandBuffer,const VkCommandBufferBeginInfo*);
static VkResult (*pEndCommandBuffer)(VkCommandBuffer);
static void (*pCmdBindPipeline)(VkCommandBuffer,uint32_t,VkPipeline);
static void (*pCmdBindDescriptorSets)(VkCommandBuffer,uint32_t,VkPipelineLayout,uint32_t,uint32_t,const VkDescriptorSet*,uint32_t,const uint32_t*);
static void (*pCmdPushConstants)(VkCommandBuffer,VkPipelineLayout,uint32_t,uint32_t,uint32_t,const void*);
static void (*pCmdDispatch)(VkCommandBuffer,uint32_t,uint32_t,uint32_t);
static VkResult (*pCreateFence)(VkDevice,const VkFenceCreateInfo*,const void*,VkFence*);
static VkResult (*pQueueSubmit)(VkQueue,uint32_t,const VkSubmitInfo*,VkFence);
static VkResult (*pWaitForFences)(VkDevice,uint32_t,const VkFence*,uint32_t,uint64_t);
static VkResult (*pResetFences)(VkDevice,uint32_t,const VkFence*);
static VkResult (*pQueueWaitIdle)(VkQueue);
#define LD(n) do{ p##n = (void*)dlsym(lib,"vk" #n); if(!p##n){ printf("ERR dlsym vk%s\n", #n); return 1; } }while(0)
#define CK(x) do{ VkResult r=(x); if(r){ printf("ERR %s -> %d\n", #x, r); return 1; } }while(0)
static VkPhysicalDeviceMemoryProperties g_memprops;
static VkDevice g_dev; static VkQueue g_queue; static VkCommandPool g_pool; static VkFence g_fence;
static int find_type(uint32_t bits,uint32_t want){
  for(uint32_t i=0;i<g_memprops.memoryTypeCount;i++)
    if((bits>>i & 1u) && (g_memprops.memoryTypes[i].propertyFlags & want)==want) return (int)i;
  return -1;
}
static int make_buf(VkDeviceSize size,uint32_t usage,uint32_t want,VkBuffer*buf,VkDeviceMemory*mem){
  VkBufferCreateInfo bi={0}; bi.sType=12; bi.size=size; bi.usage=usage; bi.sharingMode=0;
  CK(pCreateBuffer(g_dev,&bi,NULL,buf));
  VkMemoryRequirements req; pGetBufferMemoryRequirements(g_dev,*buf,&req);
  int t=find_type(req.memoryTypeBits,want);
  if(t<0){ printf("ERR no memory type for want=%u\n",want); return 1; }
  VkMemoryAllocateInfo ai={0}; ai.sType=5; ai.allocationSize=req.size; ai.memoryTypeIndex=(uint32_t)t;
  CK(pAllocateMemory(g_dev,&ai,NULL,mem));
  CK(pBindBufferMemory(g_dev,*buf,*mem,0));
  return 0;
}
static uint32_t* read_spv(const char*path,size_t*bytes){
  FILE*f=fopen(path,"rb"); if(!f){ printf("ERR open %s\n",path); exit(1); }
  fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
  uint32_t*code=malloc((size_t)n); if(fread(code,1,(size_t)n,f)!=(size_t)n){ printf("ERR read %s\n",path); exit(1); }
  fclose(f); *bytes=(size_t)n; return code;
}
static VkPipeline make_pipe(const char*spv,VkPipelineLayout layout){
  size_t n; uint32_t*code=read_spv(spv,&n);
  VkShaderModuleCreateInfo sm={0}; sm.sType=16; sm.codeSize=n; sm.pCode=code;
  VkShaderModule mod; CK(pCreateShaderModule(g_dev,&sm,NULL,&mod));
  VkComputePipelineCreateInfo ci={0}; ci.sType=29; ci.stage.sType=18; ci.stage.stage=0x20;
  ci.stage.module=mod; ci.stage.pName="main"; ci.layout=layout; ci.basePipelineIndex=-1;
  VkPipeline pipe; CK(pCreateComputePipelines(g_dev,0,1,&ci,NULL,&pipe));
  free(code); return pipe;
}
static double run_dispatch(VkPipeline pipe,VkPipelineLayout layout,VkDescriptorSet set,const void*push,uint32_t psz,uint32_t groups){
  VkCommandBufferAllocateInfo ca={0}; ca.sType=40; ca.commandPool=g_pool; ca.level=0; ca.commandBufferCount=1;
  VkCommandBuffer cb; CK(pAllocateCommandBuffers(g_dev,&ca,&cb));
  VkCommandBufferBeginInfo bb={0}; bb.sType=42;
  CK(pBeginCommandBuffer(cb,&bb));
  pCmdBindPipeline(cb,1,pipe);
  pCmdBindDescriptorSets(cb,1,layout,0,1,&set,0,NULL);
  if(push) pCmdPushConstants(cb,layout,0x20,0,psz,push);
  pCmdDispatch(cb,groups,1,1);
  CK(pEndCommandBuffer(cb));
  VkSubmitInfo si={0}; si.sType=4; si.commandBufferCount=1; si.pCommandBuffers=&cb;
  double t0=now();
  CK(pQueueSubmit(g_queue,1,&si,g_fence));
  CK(pWaitForFences(g_dev,1,&g_fence,1,UINT64_MAX));
  double dt=now()-t0;
  CK(pResetFences(g_dev,1,&g_fence));
  return dt;
}
int main(int argc,char**argv){
  const char*dir = argc>1 ? argv[1] : ".";
  void*lib=dlopen("libvulkan.so.1",RTLD_NOW);
  if(!lib){ printf("ERR dlopen libvulkan\n"); return 1; }
  LD(CreateInstance); LD(EnumeratePhysicalDevices); LD(GetPhysicalDeviceProperties);
  LD(GetPhysicalDeviceQueueFamilyProperties); LD(CreateDevice); LD(GetDeviceQueue);
  LD(CreateBuffer); LD(GetBufferMemoryRequirements); LD(GetPhysicalDeviceMemoryProperties);
  LD(AllocateMemory); LD(BindBufferMemory); LD(MapMemory); LD(UnmapMemory);
  LD(CreateShaderModule); LD(CreateDescriptorSetLayout); LD(CreatePipelineLayout);
  LD(CreateComputePipelines); LD(CreateDescriptorPool); LD(AllocateDescriptorSets);
  LD(UpdateDescriptorSets); LD(CreateCommandPool); LD(AllocateCommandBuffers);
  LD(BeginCommandBuffer); LD(EndCommandBuffer); LD(CmdBindPipeline); LD(CmdBindDescriptorSets);
  LD(CmdPushConstants); LD(CmdDispatch); LD(CreateFence); LD(QueueSubmit); LD(WaitForFences);
  LD(ResetFences); LD(QueueWaitIdle);
  VkApplicationInfo app={0}; app.sType=0; app.pApplicationName="vkprobe"; app.apiVersion=(1u<<22)|(2u<<12);
  VkInstanceCreateInfo ii={0}; ii.sType=1; ii.pApplicationInfo=&app;
  VkInstance inst; CK(pCreateInstance(&ii,NULL,&inst));
  uint32_t ndev=0; CK(pEnumeratePhysicalDevices(inst,&ndev,NULL));
  VkPhysicalDevice devs[8]; CK(pEnumeratePhysicalDevices(inst,&ndev,devs));
  VkPhysicalDevice phys=0; char devname[256]="?"; char propsbuf[8192];
  for(uint32_t i=0;i<ndev;i++){
    memset(propsbuf,0,sizeof(propsbuf)); pGetPhysicalDeviceProperties(devs[i],propsbuf);
    uint32_t dtype; memcpy(&dtype,propsbuf+16,4);
    if(dtype==1||dtype==2){ phys=devs[i]; memcpy(devname,propsbuf+20,255); devname[255]=0; break; }
  }
  if(!phys){ printf("ERR no GPU device\n"); return 1; }
  printf("DEVICE %s (Vulkan/RADV)\n",devname);
  uint32_t nqf=0; pGetPhysicalDeviceQueueFamilyProperties(phys,&nqf,NULL);
  VkQueueFamilyProperties qfs[16]; if(nqf>16)nqf=16;
  pGetPhysicalDeviceQueueFamilyProperties(phys,&nqf,qfs);
  int qfam=-1; for(uint32_t i=0;i<nqf;i++) if(qfs[i].queueFlags & 0x2u){ qfam=(int)i; break; }
  if(qfam<0){ printf("ERR no compute queue\n"); return 1; }
  float prio=1.0f;
  VkDeviceQueueCreateInfo dq={0}; dq.sType=2; dq.queueFamilyIndex=(uint32_t)qfam; dq.queueCount=1; dq.pQueuePriorities=&prio;
  VkDeviceCreateInfo di={0}; di.sType=3; di.queueCreateInfoCount=1; di.pQueueCreateInfos=&dq;
  CK(pCreateDevice(phys,&di,NULL,&g_dev));
  pGetDeviceQueue(g_dev,(uint32_t)qfam,0,&g_queue);
  pGetPhysicalDeviceMemoryProperties(phys,&g_memprops);
  VkCommandPoolCreateInfo cp={0}; cp.sType=39; cp.queueFamilyIndex=(uint32_t)qfam;
  CK(pCreateCommandPool(g_dev,&cp,NULL,&g_pool));
  VkFenceCreateInfo fc={0}; fc.sType=44;
  CK(pCreateFence(g_dev,&fc,NULL,&g_fence));
  /* descriptor pool: 3 sets, up to 4 storage buffers */
  VkDescriptorPoolSize ps={0}; ps.type=7; ps.descriptorCount=4;
  VkDescriptorPoolCreateInfo dp={0}; dp.sType=33; dp.maxSets=3; dp.poolSizeCount=1; dp.pPoolSizes=&ps;
  VkDescriptorPool pool; CK(pCreateDescriptorPool(g_dev,&dp,NULL,&pool));
  /* layouts: L1 = 1 storage buffer; L2 = 2 storage buffers. Push range only on L1 layout. */
  VkDescriptorSetLayoutBinding b1={0}; b1.binding=0; b1.descriptorType=7; b1.descriptorCount=1; b1.stageFlags=0x20;
  VkDescriptorSetLayoutCreateInfo lc1={0}; lc1.sType=32; lc1.bindingCount=1; lc1.pBindings=&b1;
  VkDescriptorSetLayout lay1; CK(pCreateDescriptorSetLayout(g_dev,&lc1,NULL,&lay1));
  VkDescriptorSetLayoutBinding b2[2]; b2[0]=b1; b2[1]=b1; b2[1].binding=1;
  VkDescriptorSetLayoutCreateInfo lc2={0}; lc2.sType=32; lc2.bindingCount=2; lc2.pBindings=b2;
  VkDescriptorSetLayout lay2; CK(pCreateDescriptorSetLayout(g_dev,&lc2,NULL,&lay2));
  VkPushConstantRange pcr={0}; pcr.stageFlags=0x20; pcr.offset=0; pcr.size=4;
  VkPipelineLayoutCreateInfo pl1={0}; pl1.sType=30; pl1.setLayoutCount=1; pl1.pSetLayouts=&lay1; pl1.pushConstantRangeCount=1; pl1.pPushConstantRanges=&pcr;
  VkPipelineLayout play1; CK(pCreatePipelineLayout(g_dev,&pl1,NULL,&play1));
  VkPipelineLayoutCreateInfo pl2={0}; pl2.sType=30; pl2.setLayoutCount=1; pl2.pSetLayouts=&lay2;
  VkPipelineLayout play2; CK(pCreatePipelineLayout(g_dev,&pl2,NULL,&play2));
  char path[512];
  snprintf(path,sizeof(path),"%s/fma32_wg64.spv",dir);  VkPipeline p_wg64=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma32_wg128.spv",dir); VkPipeline p_wg128=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma32_wg256.spv",dir); VkPipeline p_wg256=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma32_wg512.spv",dir); VkPipeline p_wg512=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma32_ilp.spv",dir);  VkPipeline p_ilp=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma64.spv",dir);      VkPipeline p_64=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/fma64x2.spv",dir);    VkPipeline p_64x2=make_pipe(path,play1);
  snprintf(path,sizeof(path),"%s/copy.spv",dir);       VkPipeline pipecp=make_pipe(path,play2);
  VkBuffer outbuf; VkDeviceMemory outmem;
  if(make_buf(64,0x20,0x2|0x4,&outbuf,&outmem)) return 1;
  VkDescriptorSetAllocateInfo sa={0}; sa.sType=34; sa.descriptorPool=pool; sa.descriptorSetCount=1; sa.pSetLayouts=&lay1;
  VkDescriptorSet set1; CK(pAllocateDescriptorSets(g_dev,&sa,&set1));
  VkDescriptorBufferInfo obi={0}; obi.buffer=outbuf; obi.offset=0; obi.range=64;
  VkWriteDescriptorSet wr={0}; wr.sType=35; wr.dstSet=set1; wr.dstBinding=0; wr.descriptorCount=1; wr.descriptorType=7; wr.pBufferInfo=&obi;
  pUpdateDescriptorSets(g_dev,1,&wr,0,NULL);
  struct T { const char* label; VkPipeline pipe; uint32_t groups; int K; double flop_per_iter; double threads; } tests[] = {
    { "FP32 WG64",  p_wg64,  4608, 4000, 32.0, 294912.0 },
    { "FP32 WG128", p_wg128, 2304, 4000, 32.0, 294912.0 },
    { "FP32 WG256", p_wg256, 1152, 4000, 32.0, 294912.0 },
    { "FP32 WG512", p_wg512,  576, 4000, 32.0, 294912.0 },
    { "FP32 ILP4",  p_ilp,   1152, 2000, 64.0, 294912.0 },
    { "FP64 BASE",  p_64,     576, 2000,  8.0, 147456.0 },
    { "FP64 ILP2",  p_64x2,   576, 1000, 16.0, 147456.0 },
  };
  for(unsigned ti=0; ti<sizeof(tests)/sizeof(tests[0]); ti++){
    struct T* t=&tests[ti]; double gf=t->threads*t->K*t->flop_per_iter/1e9;
    for(int rep=0;rep<3;rep++){ double dt=run_dispatch(t->pipe,play1,set1,&t->K,4,t->groups);
      printf("%s rep%d %.1f GFLOPS (%.3f s, %.2f GFLOP)\n",t->label,rep+1,gf/dt,dt,gf); }
  }
  { void*m; CK(pMapMemory(g_dev,outmem,0,64,0,&m)); float v; memcpy(&v,m,4); pUnmapMemory(g_dev,outmem);
    printf("SANITY out[0]=%f\n",(double)v); }
  { VkBuffer src,dst; VkDeviceMemory sm,dm; VkDeviceSize bytes=67108864ull*4;
    if(make_buf(bytes,0x20,0x1,&src,&sm)){ printf("WARN copy: no DEVICE_LOCAL src, retrying host-visible\n"); if(make_buf(bytes,0x20,0x2|0x4,&src,&sm)) return 1; }
    if(make_buf(bytes,0x20,0x1,&dst,&dm)){ printf("WARN copy: no DEVICE_LOCAL dst, retrying host-visible\n"); if(make_buf(bytes,0x20,0x2|0x4,&dst,&dm)) return 1; }
    VkDescriptorSetAllocateInfo sa2={0}; sa2.sType=34; sa2.descriptorPool=pool; sa2.descriptorSetCount=1; sa2.pSetLayouts=&lay2;
    VkDescriptorSet set2; CK(pAllocateDescriptorSets(g_dev,&sa2,&set2));
    VkDescriptorBufferInfo bi2[2]; bi2[0].buffer=src; bi2[0].offset=0; bi2[0].range=bytes; bi2[1].buffer=dst; bi2[1].offset=0; bi2[1].range=bytes;
    VkWriteDescriptorSet wr2[2]; wr2[0]=wr; wr2[0].dstSet=set2; wr2[0].dstBinding=0; wr2[0].pBufferInfo=&bi2[0];
    wr2[1]=wr; wr2[1].dstSet=set2; wr2[1].dstBinding=1; wr2[1].pBufferInfo=&bi2[1];
    pUpdateDescriptorSets(g_dev,2,wr2,0,NULL);
    double best=1e9; for(int rep=0;rep<5;rep++){ double dt=run_dispatch(pipecp,play2,set2,NULL,0,262144); if(dt<best)best=dt; }
    double gb=2.0*67108864.0*4/1e9; printf("BW %.1f GB/s (best %.3f s, %.2f GB moved)\n",gb/best,best,gb); }
  CK(pQueueWaitIdle(g_queue));
  printf("VKPROBE2 DONE\n");
  return 0;
}
