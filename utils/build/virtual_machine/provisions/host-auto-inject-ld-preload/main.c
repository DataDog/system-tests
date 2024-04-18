void
_start()
{
        asm("mov $60,%rax; mov $0,%rdi; syscall");
}