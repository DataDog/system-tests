#include <stdio.h>
// C program used to add as library in the ld-preload
int puts(const char *__s)
{
    return printf("New puts\n");
    
}