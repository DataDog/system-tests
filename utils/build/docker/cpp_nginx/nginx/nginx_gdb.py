import gdb


class NgxChainPrinter(gdb.Command):
    def __init__(self):
        super(NgxChainPrinter, self).__init__("ngx_chain_print", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        chain_ptr = gdb.parse_and_eval(arg)
        total_unread = 0

        while chain_ptr:
            chain_addr = int(chain_ptr)
            print(f"ngx_chain_t[0x{chain_addr:x}]")

            buf_ptr = chain_ptr["buf"]
            if buf_ptr:
                buf_addr = int(buf_ptr)
                start = buf_ptr["start"]
                end = buf_ptr["end"]
                pos = buf_ptr["pos"]
                last = buf_ptr["last"]
                buf_size = int(end - start)
                unread_size = int(last - pos)
                total_unread = total_unread + unread_size

                flag_names = [
                    "temporary",
                    "memory",
                    "mmap",
                    "recycled",
                    "in_file",
                    "flush",
                    "sync",
                    "last_buf",
                    "last_in_chain",
                    "last_shadow",
                    "temp_file",
                ]
                flags_set = []
                for flag in flag_names:
                    try:
                        if int(buf_ptr[flag]) != 0:
                            flags_set.append(flag)
                    except Exception as e:
                        print(f"Error reading flag {flag}: {e}")
                        continue

                data = pos.string(length=unread_size) if unread_size > 0 else ""

                print(f"  buf[0x{buf_addr:x}, size={buf_size}] unread[{unread_size}]")
                if flags_set:
                    print("    flags: " + " ".join(flags_set))
                print(f'    "{data}"')

            chain_ptr = chain_ptr["next"]

        print(f"total unread: {total_unread}")


NgxChainPrinter()


class NgxHeadersPrinter(gdb.Command):
    def __init__(self):
        super(NgxHeadersPrinter, self).__init__("ngx_headers_print", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        request_ptr = gdb.parse_and_eval(arg)
        headers_list = request_ptr["headers_in"]["headers"]

        print(f"Headers in request[0x{int(request_ptr):x}]:")

        # Start with the first part
        part_ptr = headers_list["part"].address
        header_count = 0

        while part_ptr:
            part_addr = int(part_ptr)
            nelts = int(part_ptr["nelts"])
            elts = part_ptr["elts"]

            print(f"  part[0x{part_addr:x}] nelts={nelts}")

            if nelts > 0 and elts:
                # Cast elts to ngx_table_elt_t pointer
                table_elt_type = gdb.lookup_type("ngx_table_elt_t").pointer()
                table_elts = elts.cast(table_elt_type)

                for i in range(nelts):
                    header = table_elts[i]
                    header_addr = int(header.address)

                    try:
                        # Extract key and value strings
                        key_data = header["key"]["data"]
                        key_len = int(header["key"]["len"])
                        value_data = header["value"]["data"]
                        value_len = int(header["value"]["len"])

                        key_str = key_data.string(length=key_len) if key_len > 0 else ""
                        value_str = value_data.string(length=value_len) if value_len > 0 else ""

                        hash_val = int(header["hash"])

                        print(f"    [{i}] header[0x{header_addr:x}] hash=0x{hash_val:x}")
                        print(f'        "{key_str}": "{value_str}"')

                        header_count += 1

                    except Exception as e:
                        print(f"    [{i}] Error reading header: {e}")
                        continue

            # Move to next part
            part_ptr = part_ptr["next"]

        print(f"Total headers: {header_count}")


NgxHeadersPrinter()
