/* JUPI benchmark adaptation: variable 720p/1080p offscreen target and individual glFinish wall-time samples. Based on the retained ROACH-2 qualification probe; this is a checkerboard microbenchmark, not game FPS. */
/* GPT Codex - ROACH-2
 * Bounded EGL/GLES2 pbuffer rendering and readback qualification probe.
 * Build: cc -std=c11 -O2 -Wall -Wextra -Wpedantic gpu_probe.c \
 *           -o gpu_probe -lEGL -lGLESv2
 * Run under an external timeout: timeout 30s ./gpu_probe --output NEW.ppm
 * Exit: 0 = verified rendering with no recognized software renderer;
 *       1 = EGL/GL/rendering failure; 2 = usage; 3 = software renderer;
 *       4 = artifact write failure. Renderer strings do not attest hardware.
 * Driver calls and filesystem writes require an external timeout if they hang.
 */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static int WIDTH = 1280, HEIGHT = 720;
enum { TILE = 8, DEFAULT_FRAMES = 180,
       MAX_FRAMES = 600, MAX_ERROR_DRAIN = 16 };

static unsigned int gl_error_count;
static unsigned int egl_error_count;

/* Keep all output one ASCII key/value record per line, even for driver logs. */
static void print_string(const char *key, const char *value)
{
    const unsigned char *p = (const unsigned char *)value;
    printf("%s=\"", key);
    if (p != NULL) {
        for (size_t n = 0; p[n] != '\0' && n < 16384; ++n) {
            unsigned char c = p[n];
            if (c == '\\' || c == '"') printf("\\%c", c);
            else if (c >= 32 && c <= 126) putchar(c);
            else printf("\\x%02x", (unsigned int)c);
        }
    }
    puts("\"");
}

static double now_seconds(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) return -1.0;
    return (double)t.tv_sec + (double)t.tv_nsec / 1000000000.0;
}

static void print_elapsed(const char *key, double begin, double end)
{
    if (begin >= 0.0 && end >= begin)
        printf("%s=%.3f\n", key, (end - begin) * 1000.0);
    else
        printf("%s=UNAVAILABLE\n", key);
}

static void egl_failure(const char *step)
{
    ++egl_error_count;
    print_string("egl_failed_step", step);
    printf("egl_error=0x%04x\n", (unsigned int)eglGetError());
}

static int check_gl(const char *step)
{
    int ok = 1;
    for (int i = 0; i < MAX_ERROR_DRAIN; ++i) {
        GLenum error = glGetError();
        if (error == GL_NO_ERROR) return ok;
        ok = 0;
        ++gl_error_count;
        print_string("gl_failed_step", step);
        printf("gl_error=0x%04x\n", (unsigned int)error);
    }
    puts("gl_error_drain=LIMIT_REACHED");
    return 0;
}

static unsigned char ascii_lower(unsigned char c)
{
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c + ('a' - 'A')) : c;
}

static int contains_ci(const char *text, const char *needle)
{
    size_t text_length, needle_length;
    if (text == NULL) return 0;
    text_length = strlen(text);
    needle_length = strlen(needle);
    if (needle_length > text_length) return 0;
    for (size_t i = 0; i <= text_length - needle_length; ++i) {
        size_t j;
        for (j = 0; j < needle_length; ++j) {
            if (ascii_lower((unsigned char)text[i + j]) !=
                ascii_lower((unsigned char)needle[j])) break;
        }
        if (j == needle_length) return 1;
    }
    return 0;
}

static const char *software_marker(const char *renderer, const char *vendor,
                                   const char *version)
{
    static const char *const markers[] = {
        "llvmpipe", "softpipe", "swrast", "software rasterizer", "software",
        "swiftshader", "lavapipe", "gdi generic", "basic render driver"
    };
    for (size_t i = 0; i < sizeof markers / sizeof markers[0]; ++i) {
        if (contains_ci(renderer, markers[i]) || contains_ci(vendor, markers[i]) ||
            contains_ci(version, markers[i])) return markers[i];
    }
    return NULL;
}

static GLuint compile_shader(GLenum type, const char *source, const char *label)
{
    GLuint shader = glCreateShader(type);
    GLint compiled = GL_FALSE;
    GLint log_length = 0;
    char log[4096];
    GLsizei written = 0;
    if (shader != 0) {
        glShaderSource(shader, 1, &source, NULL);
        glCompileShader(shader);
        glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &log_length);
        if (log_length > 1) {
            glGetShaderInfoLog(shader, (GLsizei)sizeof log - 1, &written, log);
            log[written >= 0 && (size_t)written < sizeof log ?
                (size_t)written : sizeof log - 1] = '\0';
            print_string(label, log);
            if ((size_t)log_length > sizeof log) puts("shader_log_truncated=YES");
        }
    }
    printf("%s_compile=%s\n", label, compiled == GL_TRUE ? "PASS" : "FAIL");
    if (!check_gl(label) || compiled != GL_TRUE) {
        if (shader != 0) glDeleteShader(shader);
        return 0;
    }
    return shader;
}

/* O_EXCL provides the no-overwrite guarantee, including existing symlinks. */
static int write_ppm(const char *path, const unsigned char *pixels)
{
    unsigned char row[WIDTH * 3];
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    FILE *file;
    int ok = 1;
    if (fd < 0) {
        print_string("artifact_error", strerror(errno));
        puts("artifact_status=NOT_CREATED");
        return 0;
    }
    file = fdopen(fd, "wb");
    if (file == NULL) {
        int saved_errno = errno;
        (void)close(fd);
        print_string("artifact_error", strerror(saved_errno));
        puts("artifact_status=EMPTY_FILE_RETAINED");
        return 0;
    }
    if (fprintf(file, "P6\n# GLES2 checkerboard; top-down rows; alpha checked separately\n%d %d\n255\n",
                WIDTH, HEIGHT) < 0) ok = 0;
    for (int y = HEIGHT - 1; y >= 0 && ok; --y) {
        for (int x = 0; x < WIDTH; ++x) {
            size_t source = ((size_t)y * WIDTH + (size_t)x) * 4;
            for (int c = 0; c < 3; ++c)
                row[x * 3 + c] = pixels[source + (size_t)c];
        }
        if (fwrite(row, 1, sizeof row, file) != sizeof row) ok = 0;
    }
    if (fclose(file) != 0) ok = 0;
    if (!ok) {
        puts("artifact_status=WRITE_FAILED_PARTIAL_FILE_RETAINED");
        return 0;
    }
    print_string("artifact_path", path);
    puts("artifact_format=PPM_P6_RGB_TOP_DOWN");
    puts("artifact_status=WRITTEN");
    return 1;
}

static void usage(const char *program)
{
    fprintf(stderr, "Usage: %s --output NEW.ppm [--frames 1..%d]\n",
            program, MAX_FRAMES);
}

int main(int argc, char **argv)
{
    const char *resolution = getenv("JUPI_BENCH_RESOLUTION");
    if (resolution && strcmp(resolution,"1920x1080")==0) { WIDTH=1920; HEIGHT=1080; }
    static const char vertex_source[] =
        "attribute vec2 a_position;\n"
        "void main() { gl_Position = vec4(a_position, 0.0, 1.0); }\n";
    static const char fragment_source[] =
        "precision mediump float;\n"
        "void main() {\n"
        "  float v = mod(floor(gl_FragCoord.x / 8.0) +\n"
        "                floor(gl_FragCoord.y / 8.0), 2.0);\n"
        "  gl_FragColor = vec4(v, v, v, 1.0);\n"
        "}\n";
    static const GLfloat vertices[] = {
        -1.0f, -1.0f, 1.0f, -1.0f, -1.0f, 1.0f,
        -1.0f, 1.0f, 1.0f, -1.0f, 1.0f, 1.0f
    };
    const EGLint config_attributes[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8, EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8, EGL_DEPTH_SIZE, 0, EGL_STENCIL_SIZE, 0,
        EGL_SAMPLE_BUFFERS, 0, EGL_NONE
    };
    EGLint surface_attributes[] = { EGL_WIDTH, WIDTH, EGL_HEIGHT, HEIGHT,
                                         EGL_NONE };
    const EGLint context_attributes[] = { EGL_CONTEXT_CLIENT_VERSION, 2,
                                         EGL_NONE };
    const char *output_path = NULL;
    const char *marker = NULL;
    EGLDisplay display = EGL_NO_DISPLAY;
    EGLSurface surface = EGL_NO_SURFACE;
    EGLContext context = EGL_NO_CONTEXT;
    EGLConfig config;
    EGLint count = 0, major = 0, minor = 0, surface_width = 0, surface_height = 0;
    GLuint vertex_shader = 0, fragment_shader = 0, program = 0, buffer = 0;
    unsigned char *pixels = NULL;
    unsigned int mismatched_pixels = 0, mismatched_channels = 0;
    unsigned int alpha_mismatches = 0, black_pixels = 0, white_pixels = 0;
    int frames = DEFAULT_FRAMES, frames_set = 0;
    int initialized = 0, current = 0, exit_code = 1, completed = 0;
    double begin = now_seconds(), phase_begin, phase_end;

    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--output") == 0 && i + 1 < argc && output_path == NULL) {
            output_path = argv[++i];
        } else if (strcmp(argv[i], "--frames") == 0 && i + 1 < argc && !frames_set) {
            char *end = NULL;
            long parsed;
            errno = 0;
            parsed = strtol(argv[++i], &end, 10);
            if (errno != 0 || end == argv[i] || *end != '\0' ||
                parsed < 1 || parsed > MAX_FRAMES) {
                usage(argv[0]);
                return 2;
            }
            frames = (int)parsed;
            frames_set = 1;
        } else {
            usage(argv[0]);
            return 2;
        }
    }
    if (output_path == NULL || output_path[0] == '\0') {
        usage(argv[0]);
        return 2;
    }
    /* Make progress visible to a caller's external timeout/log capture. */
    (void)setvbuf(stdout, NULL, _IOLBF, 0);
    puts("probe=GPT_Codex_ROACH_2_GLES2_CHECKERBOARD_V1");
    printf("width=%d\nheight=%d\ntile_size=%d\nframes_requested=%d\n",
           WIDTH, HEIGHT, TILE, frames);
    puts("readback_origin=BOTTOM_LEFT");
    puts("hardware_attestation=NOT_PROVIDED");
    puts("software_detection=KNOWN_RENDERER_STRING_MARKERS_ONLY");
    pixels = malloc((size_t)WIDTH * HEIGHT * 4);
    if (pixels == NULL) {
        puts("error=PIXEL_ALLOCATION_FAILED");
        goto cleanup;
    }
    phase_begin = now_seconds();
    display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (display == EGL_NO_DISPLAY) { egl_failure("eglGetDisplay"); goto cleanup; }
    if (!eglInitialize(display, &major, &minor)) {
        egl_failure("eglInitialize"); goto cleanup;
    }
    initialized = 1;
    printf("egl_initialized_version=%d.%d\n", (int)major, (int)minor);
    {
        const char *vendor = eglQueryString(display, EGL_VENDOR);
        const char *version = eglQueryString(display, EGL_VERSION);
        const char *apis = eglQueryString(display, EGL_CLIENT_APIS);
        if (vendor == NULL || version == NULL || apis == NULL) {
            egl_failure("eglQueryString"); goto cleanup;
        }
        print_string("egl_vendor", vendor);
        print_string("egl_version", version);
        print_string("egl_client_apis", apis);
    }
    if (!eglBindAPI(EGL_OPENGL_ES_API)) { egl_failure("eglBindAPI"); goto cleanup; }
    if (!eglChooseConfig(display, config_attributes, &config, 1, &count)) {
        egl_failure("eglChooseConfig"); goto cleanup;
    }
    if (count < 1) { puts("error=NO_MATCHING_EGL_CONFIG"); goto cleanup; }
    {
        const EGLint attributes[] = { EGL_CONFIG_ID, EGL_RED_SIZE, EGL_GREEN_SIZE,
            EGL_BLUE_SIZE, EGL_ALPHA_SIZE, EGL_SAMPLE_BUFFERS, EGL_SAMPLES };
        const char *keys[] = { "egl_config_id", "egl_red_bits", "egl_green_bits",
            "egl_blue_bits", "egl_alpha_bits", "egl_sample_buffers", "egl_samples" };
        for (size_t i = 0; i < sizeof attributes / sizeof attributes[0]; ++i) {
            EGLint value = 0;
            if (!eglGetConfigAttrib(display, config, attributes[i], &value)) {
                egl_failure("eglGetConfigAttrib"); goto cleanup;
            }
            printf("%s=%d\n", keys[i], (int)value);
        }
    }
    surface = eglCreatePbufferSurface(display, config, surface_attributes);
    if (surface == EGL_NO_SURFACE) {
        egl_failure("eglCreatePbufferSurface"); goto cleanup;
    }
    if (!eglQuerySurface(display, surface, EGL_WIDTH, &surface_width) ||
        !eglQuerySurface(display, surface, EGL_HEIGHT, &surface_height)) {
        egl_failure("eglQuerySurface"); goto cleanup;
    }
    if (surface_width != WIDTH || surface_height != HEIGHT) {
        puts("error=UNEXPECTED_PBUFFER_SIZE"); goto cleanup;
    }
    context = eglCreateContext(display, config, EGL_NO_CONTEXT, context_attributes);
    if (context == EGL_NO_CONTEXT) { egl_failure("eglCreateContext"); goto cleanup; }
    if (!eglMakeCurrent(display, surface, surface, context)) {
        egl_failure("eglMakeCurrent"); goto cleanup;
    }
    current = 1;
    phase_end = now_seconds();
    print_elapsed("egl_setup_ms", phase_begin, phase_end);
    {
        const char *vendor = (const char *)glGetString(GL_VENDOR);
        const char *renderer = (const char *)glGetString(GL_RENDERER);
        const char *version = (const char *)glGetString(GL_VERSION);
        const char *glsl = (const char *)glGetString(GL_SHADING_LANGUAGE_VERSION);
        int strings_ok = check_gl("glGetString");
        if (!strings_ok || vendor == NULL || renderer == NULL || version == NULL || glsl == NULL) {
            puts("error=GL_IDENTIFICATION_FAILED"); goto cleanup;
        }
        print_string("gl_vendor", vendor);
        print_string("gl_renderer", renderer);
        print_string("gl_version", version);
        print_string("glsl_version", glsl);
        marker = software_marker(renderer, vendor, version);
        printf("software_renderer_detected=%s\n", marker == NULL ? "NO_KNOWN_MARKER" : "YES");
        if (marker != NULL) print_string("software_renderer_marker", marker);
    }
    phase_begin = now_seconds();
    vertex_shader = compile_shader(GL_VERTEX_SHADER, vertex_source, "vertex_shader");
    if (vertex_shader == 0) goto cleanup;
    fragment_shader = compile_shader(GL_FRAGMENT_SHADER, fragment_source, "fragment_shader");
    if (fragment_shader == 0) goto cleanup;
    program = glCreateProgram();
    if (program == 0) {
        puts("error=PROGRAM_CREATION_FAILED");
        (void)check_gl("glCreateProgram");
        goto cleanup;
    }
    glAttachShader(program, vertex_shader);
    glAttachShader(program, fragment_shader);
    glBindAttribLocation(program, 0, "a_position");
    glLinkProgram(program);
    {
        GLint linked = GL_FALSE, log_length = 0;
        GLsizei written = 0;
        char log[4096];
        glGetProgramiv(program, GL_LINK_STATUS, &linked);
        glGetProgramiv(program, GL_INFO_LOG_LENGTH, &log_length);
        if (log_length > 1) {
            glGetProgramInfoLog(program, (GLsizei)sizeof log - 1, &written, log);
            log[written >= 0 && (size_t)written < sizeof log ?
                (size_t)written : sizeof log - 1] = '\0';
            print_string("program_link_log", log);
            if ((size_t)log_length > sizeof log) puts("program_log_truncated=YES");
        }
        printf("program_link=%s\n", linked == GL_TRUE ? "PASS" : "FAIL");
        if (!check_gl("program_link") || linked != GL_TRUE) goto cleanup;
    }
    print_elapsed("shader_setup_ms", phase_begin, now_seconds());
    glUseProgram(program);
    glGenBuffers(1, &buffer);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glBufferData(GL_ARRAY_BUFFER, (GLsizeiptr)sizeof vertices, vertices, GL_STATIC_DRAW);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, (const void *)0);
    glEnableVertexAttribArray(0);
    glViewport(0, 0, WIDTH, HEIGHT);
    glDisable(GL_DITHER);
    glDisable(GL_BLEND);
    glDisable(GL_SCISSOR_TEST);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_STENCIL_TEST);
    glDisable(GL_CULL_FACE);
    glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    /* Magenta sentinel makes a missing draw visibly and numerically fail. */
    glClearColor(1.0f, 0.0f, 1.0f, 0.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glFinish();
    if (!check_gl("render_setup") || buffer == 0) goto cleanup;
    phase_begin = now_seconds();
    for (int i = 0; i < 10; ++i) { glDrawArrays(GL_TRIANGLES, 0, 6); glFinish(); }
    phase_begin = now_seconds();
    for (int i = 0; i < frames; ++i) {
        double frame_begin=now_seconds();
        glDrawArrays(GL_TRIANGLES, 0, 6); glFinish();
        printf("frame_ms_%d=%.6f\n", i, (now_seconds()-frame_begin)*1000.0);
    }
    glFinish();
    phase_end = now_seconds();
    print_elapsed("draw_and_finish_ms", phase_begin, phase_end);
    printf("draw_calls_submitted=%d\n", frames);
    if (!check_gl("draw_and_finish")) goto cleanup;
    /* Sentinel initialization also makes absent/partial readback fail. */
    memset(pixels, 0x5a, (size_t)WIDTH * HEIGHT * 4);
    phase_begin = now_seconds();
    glReadPixels(0, 0, WIDTH, HEIGHT, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    glFinish();
    print_elapsed("readback_and_finish_ms", phase_begin, now_seconds());
    if (!check_gl("readback_and_finish")) goto cleanup;
    phase_begin = now_seconds();
    for (int y = 0; y < HEIGHT; ++y) {
        for (int x = 0; x < WIDTH; ++x) {
            unsigned char expected = (unsigned char)(((x / TILE + y / TILE) & 1) * 255);
            size_t offset = ((size_t)y * WIDTH + (size_t)x) * 4;
            int mismatch = 0;
            for (int c = 0; c < 4; ++c) {
                unsigned char want = c == 3 ? 255 : expected;
                if (pixels[offset + (size_t)c] != want) {
                    ++mismatched_channels;
                    mismatch = 1;
                    if (c == 3) ++alpha_mismatches;
                }
            }
            if (mismatch) {
                if (mismatched_pixels < 8) {
                    printf("mismatch_%u=x:%d,y:%d,expected:%u/%u/%u/255,actual:%u/%u/%u/%u\n",
                           mismatched_pixels, x, y, (unsigned int)expected,
                           (unsigned int)expected, (unsigned int)expected,
                           (unsigned int)pixels[offset], (unsigned int)pixels[offset + 1],
                           (unsigned int)pixels[offset + 2], (unsigned int)pixels[offset + 3]);
                }
                ++mismatched_pixels;
            }
            if (pixels[offset] == 0 && pixels[offset + 1] == 0 && pixels[offset + 2] == 0)
                ++black_pixels;
            if (pixels[offset] == 255 && pixels[offset + 1] == 255 && pixels[offset + 2] == 255)
                ++white_pixels;
        }
    }
    print_elapsed("cpu_validation_ms", phase_begin, now_seconds());
    printf("pixels_checked=%d\nchannels_checked=%d\n", WIDTH * HEIGHT, WIDTH * HEIGHT * 4);
    printf("mismatched_pixels=%u\nmismatched_channels=%u\nalpha_mismatches=%u\n",
           mismatched_pixels, mismatched_channels, alpha_mismatches);
    printf("black_pixels=%u\nwhite_pixels=%u\nexpected_each_color=%d\n",
           black_pixels, white_pixels, WIDTH * HEIGHT / 2);
    printf("pixel_validation=%s\n", mismatched_pixels == 0 ? "PASS" : "FAIL");
    completed = 1;
    /* Preserve a diagnostic image even when pixel validation or software detection fails. */
    phase_begin = now_seconds();
    if (!write_ppm(output_path, pixels)) { exit_code = 4; goto cleanup; }
    print_elapsed("artifact_write_ms", phase_begin, now_seconds());
    exit_code = mismatched_pixels != 0 ? 1 : marker != NULL ? 3 : 0;

cleanup:
    if (current) {
        if (buffer != 0) glDeleteBuffers(1, &buffer);
        if (program != 0) glDeleteProgram(program);
        if (vertex_shader != 0) glDeleteShader(vertex_shader);
        if (fragment_shader != 0) glDeleteShader(fragment_shader);
        if (!check_gl("gl_cleanup") && exit_code == 0) exit_code = 1;
        if (!eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT))
            egl_failure("eglMakeCurrent_unbind");
    }
    if (context != EGL_NO_CONTEXT && !eglDestroyContext(display, context))
        egl_failure("eglDestroyContext");
    if (surface != EGL_NO_SURFACE && !eglDestroySurface(display, surface))
        egl_failure("eglDestroySurface");
    if (initialized && !eglTerminate(display)) egl_failure("eglTerminate");
    if (egl_error_count != 0 && exit_code == 0) exit_code = 1;
    free(pixels);
    printf("validation_completed=%s\n", completed ? "YES" : "NO");
    printf("gl_error_count=%u\negl_error_count=%u\n", gl_error_count, egl_error_count);
    print_elapsed("total_ms", begin, now_seconds());
    printf("result=%s\n", exit_code == 0 ? "PASS_RENDER_VALIDATION_NO_KNOWN_SOFTWARE_MARKER" :
           exit_code == 3 ? "FAIL_SOFTWARE_RENDERER" :
           exit_code == 4 ? "FAIL_ARTIFACT_WRITE" : "FAIL_RENDER_OR_API");
    printf("exit_code=%d\n", exit_code);
    return exit_code;
}
