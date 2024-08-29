#include <microhttpd.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <stdio.h>

#define PORT 7778

static struct MHD_Daemon *daemon_;

static enum MHD_Result answer_to_connection(void *cls, struct MHD_Connection *connection,
                         const char *url, const char *method,
                         const char *version, const char *upload_data,
                         size_t *upload_data_size, void **con_cls)
{
    const char *status_str = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "status");
    const char *value = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "value");

    if (strcmp(url, "/content") != 0 || !status_str || !value)
        return MHD_NO;  // Only respond to the correct URL and if all parameters are present

    int status_code = atoi(status_str);
    if (status_code <= 0)
        return MHD_NO;  // Ensure the status code is a valid positive integer

    const char *page = value;
    struct MHD_Response *response = MHD_create_response_from_buffer(strlen(page), (void*)page, MHD_RESPMEM_MUST_COPY);
    MHD_add_response_header(response, "Content-Type", "text/html");

    int ret = MHD_queue_response(connection, status_code, response);
    MHD_destroy_response(response);
    return ret;
}

void stop_server(int signum)
{
    if (daemon_)
    {
        MHD_stop_daemon(daemon_);
        daemon_ = NULL;
        printf("Server has been stopped.\n");
    }
    exit(0);
}

int main()
{
    struct sigaction action;
    memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = stop_server;
    sigaction(SIGINT, &action, NULL);  // Handle SIGINT
    sigaction(SIGTERM, &action, NULL);  // Handle SIGTERM

    daemon_ = MHD_start_daemon(MHD_USE_INTERNAL_POLLING_THREAD, PORT, NULL, NULL,
                               &answer_to_connection, NULL, MHD_OPTION_END);
    if (!daemon_)
    {
        fprintf(stderr, "Failed to start the daemon.\n");
        return 1;
    }

    printf("Server running on port %d\n", PORT);
    pause();  // Wait for signals

    return 0;
}
