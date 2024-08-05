#include <stdio.h>
#include <dlfcn.h>

typedef int (*original_puts_t)(const char *str);

// C program used to add as library in the ld-preload
int puts(const char *str)
{
    original_puts_t original_puts;
    original_puts = (original_puts_t) dlsym(RTLD_NEXT,"puts");
    return original_puts(str);
}
