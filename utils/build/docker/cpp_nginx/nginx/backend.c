#include <fcntl.h>
#include <microhttpd.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <stdio.h>
#include <sys/stat.h>

#define PORT 7778
#define MAX_JSON_SIZE 8192

static struct MHD_Daemon *daemon_;

// Structure to hold header data for JSON construction
struct header_data {
    char *json_buffer;
    size_t buffer_size;
    size_t current_pos;
    bool first_header;
};

static ssize_t read_data(void *cls, uint64_t pos, char *buf, size_t max) {
    int fd = (int)(uintptr_t)cls;
    ssize_t num_read = read(fd, buf, max);
    if (num_read == 0) {
        return -1;
    }
    if (num_read < 0) {
        return -2;
    }
    return num_read;
}

static void close_fd(void *cls) {
    close((int)(uintptr_t)cls);
}

// Helper function to escape JSON strings
static void escape_json_string(const char *src, char *dest, size_t dest_size) {
    size_t dest_pos = 0;
    size_t src_len = strlen(src);

    for (size_t i = 0; i < src_len && dest_pos < dest_size - 1; i++) {
        switch (src[i]) {
            case '"':
                if (dest_pos < dest_size - 2) {
                    dest[dest_pos++] = '\\';
                    dest[dest_pos++] = '"';
                }
                break;
            case '\\':
                if (dest_pos < dest_size - 2) {
                    dest[dest_pos++] = '\\';
                    dest[dest_pos++] = '\\';
                }
                break;
            case '\n':
                if (dest_pos < dest_size - 2) {
                    dest[dest_pos++] = '\\';
                    dest[dest_pos++] = 'n';
                }
                break;
            case '\r':
                if (dest_pos < dest_size - 2) {
                    dest[dest_pos++] = '\\';
                    dest[dest_pos++] = 'r';
                }
                break;
            case '\t':
                if (dest_pos < dest_size - 2) {
                    dest[dest_pos++] = '\\';
                    dest[dest_pos++] = 't';
                }
                break;
            default:
                dest[dest_pos++] = src[i];
                break;
        }
    }
    dest[dest_pos] = '\0';
}

static enum MHD_Result header_iterator(void *cls, enum MHD_ValueKind kind,
                                     const char *key, const char *value) {
    struct header_data *data = (struct header_data *)cls;

    // skip if we don't have enough space
    if (data->current_pos >= data->buffer_size - 200) {
       return MHD_YES;
    }

    char escaped_key[512];
    char escaped_value[1024];

    escape_json_string(key, escaped_key, sizeof(escaped_key));
    escape_json_string(value ? value : "", escaped_value, sizeof(escaped_value));

    // add comma if not the first header
    if (!data->first_header) {
        data->current_pos += snprintf(data->json_buffer + data->current_pos,
                                    data->buffer_size - data->current_pos,
                                    ",");
    } else {
        data->first_header = false;
    }

    // Add the key-value pair
    data->current_pos += snprintf(data->json_buffer + data->current_pos,
                                data->buffer_size - data->current_pos,
                                "\"%s\":\"%s\"",
                                escaped_key, escaped_value);

    return MHD_YES;
}

static enum MHD_Result answer_to_connection(void *cls, struct MHD_Connection *connection,
                         const char *url, const char *method,
                         const char *version, const char *upload_data,
                         size_t *upload_data_size, void **con_cls)
{
    const char *status_str = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "status");
    const char *value = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "value");

    if (strcmp(url, "/read_file") == 0) {
        const char *val = MHD_lookup_connection_value (connection, MHD_GET_ARGUMENT_KIND, "file");
        if (!val) {
            return MHD_NO;
        }

        const int fd = open(val, O_RDONLY);
        if (fd < 0) {
            return MHD_NO;
        }

        struct stat st;
        if (fstat(fd, &st) != 0) {
            close(fd);
            return MHD_NO;
        }
        const size_t file_size = st.st_size;

        struct MHD_Response *response;
        if (file_size == 0) {
            response = MHD_create_response_from_callback(-1, 512, read_data, (void*)(uintptr_t)fd, close_fd);
        } else {
            response = MHD_create_response_from_fd((uint64_t)file_size, fd);
        }

        MHD_add_response_header(response, "Content-Type", "application/octet-stream");
        int ret = MHD_queue_response(connection, 200, response);
        MHD_destroy_response(response);
        return ret;
    }

    if (strcmp(url, "/returnheaders") == 0) {
        char *json_buffer = malloc(MAX_JSON_SIZE);
        if (!json_buffer) {
            return MHD_NO;
        }

        struct header_data data = {
            .json_buffer = json_buffer,
            .buffer_size = MAX_JSON_SIZE,
            .current_pos = 0,
            .first_header = true
        };

        data.current_pos += snprintf(json_buffer, MAX_JSON_SIZE, "{");

        MHD_get_connection_values(connection, MHD_HEADER_KIND, header_iterator, &data);

        data.current_pos += snprintf(json_buffer + data.current_pos,
                                   MAX_JSON_SIZE - data.current_pos, "}");

        struct MHD_Response *response = MHD_create_response_from_buffer(
            data.current_pos, json_buffer, MHD_RESPMEM_MUST_FREE);
        MHD_add_response_header(response, "Content-Type", "application/json");

        int ret = MHD_queue_response(connection, 200, response);
        MHD_destroy_response(response);
        return ret;
    }

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
