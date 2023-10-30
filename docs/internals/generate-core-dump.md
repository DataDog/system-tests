When weblog experiences segmentation fault, it may be difficult to get a core dump. Here is an helpful recipe from @sanchda : 

> * Assumes a glibc-compatible container
> * download https://github.com/sanchda/test_gcr/releases/download/v1.16.1_innerapi/libSegFault.so into the image
> * Make it executable
> * LD_PRELOAD the resulting file somewhere in the environment python will pick up
> * It’ll emit the backtrace at the crash site as well as some useful diagnostic information to stdio

For instance, on python django weblog : 

```bash
> docker run -it system_tests/weblog bash
root@x:/app# apt-get install weget
root@x:/app# wget https://github.com/sanchda/test_gcr/releases/download/v1.16.1_innerapi/libSegFault.so
root@x:/app# chmod +x libSegFault.so
root@x:/app# LD_PRELOAD=/app/libSegFault.so ddtrace-run gunicorn -w 1 -b 0.0.0.0:7777 --access-logfile - django_app.wsgi -k gevent


... And here comes the fun !!!


```
