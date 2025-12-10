#include <fcntl.h>
#include <microhttpd.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

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

// Structure to hold POST data
struct post_data {
    char *data;
    size_t size;
    size_t pos;
    struct MHD_PostProcessor *pp;
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

static void parse_form_data_to_json(const char *form_data, char *json_buffer, size_t json_size) {
    if (!form_data || !json_buffer || json_size < 50) return;

    size_t json_pos = 0;
    int ret = snprintf(json_buffer, json_size, "{\"payload\":{");
    if (ret < 0 || (size_t)ret >= json_size) {
        json_buffer[0] = '\0';
        return;
    }
    json_pos += ret;

    char *form_copy = strdup(form_data);
    if (!form_copy) {
        snprintf(json_buffer, json_size, "{\"payload\":{}}");
        return;
    }

    char *pair = strtok(form_copy, "&");
    bool first_pair = true;

    while (pair && json_pos < json_size - 10) {
        char *eq = strchr(pair, '=');
        if (eq) {
            *eq = '\0';
            char *key = pair;
            char *value = eq + 1;

            // URL decode value (basic implementation for + and %XX)
            // key should technically be decoded too
            char decoded_value[256];
            size_t i = 0, j = 0;
            while (i < strlen(value) && j < sizeof(decoded_value) - 1) {
                if (value[i] == '+') {
                    decoded_value[j] = ' ';
                } else if (value[i] == '%' && i + 2 < strlen(value)) {
                    // Simple hex decode for %XX
                    char hex[3] = {value[i+1], value[i+2], '\0'};
                    decoded_value[j] = (char)strtol(hex, NULL, 16);
                    i += 2;
                } else {
                    decoded_value[j] = value[i];
                }
                i++;
                j++;
            }
            decoded_value[j] = '\0';

            if (!first_pair) {
                ret = snprintf(json_buffer + json_pos, json_size - json_pos, ",");
                if (ret < 0 || (size_t)ret >= json_size - json_pos) break;
                json_pos += ret;
            }
            first_pair = false;

            // Determine if value is numeric (VERY roughly) or boolean
            if (strcmp(decoded_value, "true") == 0 || strcmp(decoded_value, "false") == 0) {
                ret = snprintf(json_buffer + json_pos, json_size - json_pos,
                              "\"%s\":%s", key, decoded_value);
            } else if (strspn(decoded_value, "0123456789.-") == strlen(decoded_value) && strlen(decoded_value) > 0) {
                ret = snprintf(json_buffer + json_pos, json_size - json_pos,
                              "\"%s\":%s", key, decoded_value);
            } else {
                // should escape quotes too
                ret = snprintf(json_buffer + json_pos, json_size - json_pos,
                              "\"%s\":\"%s\"", key, decoded_value);
            }

            if (ret < 0 || (size_t)ret >= json_size - json_pos) break;
            json_pos += ret;
        }
        pair = strtok(NULL, "&");
    }

    ret = snprintf(json_buffer + json_pos, json_size - json_pos, "}}");
    if (ret < 0 || (size_t)ret >= json_size - json_pos) {
        // Ensure null termination if truncated
        json_buffer[json_size - 1] = '\0';
    }

    free(form_copy);
}

// POST processor iterator callback: just append data
static enum MHD_Result post_iterator(void *cls, enum MHD_ValueKind kind,
                                    const char *key, const char *filename,
                                    const char *content_type,
                                    const char *transfer_encoding,
                                    const char *data, uint64_t off, size_t size) {
    struct post_data *post_info = (struct post_data *)cls;

    if (size == 0) return MHD_YES;

    // Append form field to our data buffer
    size_t needed = post_info->pos + 1 + strlen(key) + 1 + size; // &key=<data>
    if (needed >= post_info->size) {
        return MHD_YES; // Buffer full
    }

    if (post_info->pos > 0) {
        post_info->pos += snprintf(post_info->data + post_info->pos,
                                  post_info->size - post_info->pos, "&");
    }

    post_info->pos += snprintf(post_info->data + post_info->pos,
                              post_info->size - post_info->pos,
                              "%s=", key);

    post_info->pos += snprintf(post_info->data + post_info->pos,
                              post_info->size - post_info->pos, "%.*s", (int)size, data);

    if (post_info->pos >= post_info->size - 1) {
        post_info->pos = post_info->size - 1;
    }
    post_info->data[post_info->pos] = '\0';

    return MHD_YES;
}

static enum MHD_Result answer_to_connection(void *cls, struct MHD_Connection *connection,
                         const char *url, const char *method,
                         const char *version, const char *upload_data,
                         size_t *upload_data_size, void **con_cls)
{
    int ret;
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

    const char *tag_value = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "tag_value");

    // Handle API Security specific cases
    if (tag_value) {
        // Handle payload_in_response_body case - return JSON with form data
        if (strstr(tag_value, "payload_in_response_body") && strcmp(method, "POST") == 0) {
            struct post_data *post_info = (struct post_data *)*con_cls;

            // First call - initialize POST processor
            if (post_info == NULL) {
                post_info = malloc(sizeof(struct post_data));
                if (!post_info) return MHD_NO;

                post_info->data = malloc(8192);
                if (!post_info->data) {
                    free(post_info);
                    return MHD_NO;
                }
                post_info->size = 8192;
                post_info->pos = 0;
                post_info->data[0] = '\0';

                post_info->pp = MHD_create_post_processor(connection, 8192, post_iterator, post_info);
                if (!post_info->pp) {
                    free(post_info->data);
                    free(post_info);
                    return MHD_NO;
                }

                *con_cls = post_info;
                return MHD_YES;
            }

            // Process incoming POST data
            if (*upload_data_size > 0) {
                MHD_post_process(post_info->pp, upload_data, *upload_data_size);
                *upload_data_size = 0;
                return MHD_YES;
            }

            // Final call - generate response
            char *json_response = malloc(MAX_JSON_SIZE);
            if (!json_response) {
                MHD_destroy_post_processor(post_info->pp);
                free(post_info->data);
                free(post_info);
                return MHD_NO;
            }

            parse_form_data_to_json(post_info->data, json_response, MAX_JSON_SIZE);

            struct MHD_Response *response = MHD_create_response_from_buffer(
                strlen(json_response), json_response, MHD_RESPMEM_MUST_FREE);
            MHD_add_response_header(response, "Content-Type", "application/json");

            ret = MHD_queue_response(connection, status_code, response);
            MHD_destroy_response(response);

            MHD_destroy_post_processor(post_info->pp);
            free(post_info->data);
            free(post_info);

            return ret;
        }

        // Handle api_match_AS005 case - add x-option response header
        if (strcmp(tag_value, "api_match_AS005") == 0) {
            const char *x_option = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "X-option");

            struct MHD_Response *response = MHD_create_response_from_buffer(
                strlen(value), (void*)value, MHD_RESPMEM_MUST_COPY);
            MHD_add_response_header(response, "Content-Type", "text/html");

            if (x_option) {
                MHD_add_response_header(response, "x-option", x_option);
            }

            ret = MHD_queue_response(connection, status_code, response);
            MHD_destroy_response(response);
            return ret;
        }
    }

    const char *page = value;
    struct MHD_Response *response = MHD_create_response_from_buffer(strlen(page), (void*)page, MHD_RESPMEM_MUST_COPY);
    MHD_add_response_header(response, "Content-Type", "text/html");

    const char *content_language = MHD_lookup_connection_value(connection, MHD_GET_ARGUMENT_KIND, "content-language");
    if (content_language) {
        MHD_add_response_header(response, "Content-Language", content_language);
    }

    ret = MHD_queue_response(connection, status_code, response);
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
