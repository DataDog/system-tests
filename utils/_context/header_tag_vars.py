prefix = "http.request.headers."

class TestData:
    def __init__(self, header, value, config, tag):
        self.header = header
        self.value = value
        self.config = config
        self.tag = tag


header_tag_tests = {
    "Test_HeaderTags_Short": TestData(
        header = "header1",
        value = "val",
        config = "header1",
        tag = prefix + "header1"
    ),
    "Test_HeaderTags_Long": TestData(
        header = "header2",
        value = "val",
        config = "header2:mapped-header",
        tag = "mapped-header"
    ),
    "Test_HeaderTags_Whitespace_Header": TestData(
        header = "header3",
        value = "val",
        config = " header3 ",
        tag = prefix + "header3"
    ),
    "Test_HeaderTags_Whitespace_Tag": TestData(
        header = "header4",
        value = "val",
        config = "header4: t a g ",
        tag = "t a g"
    ),
    "Test_HeaderTags_Whitespace_Val_Short": TestData(
        header = "header5",
        value = " v a l ",
        config = "header5",
        tag = prefix + "header5"
    ),
    "Test_HeaderTags_Whitespace_Val_Long": TestData(
        header = "header6",
        value = " v a l ",
        config = "header6:tag",
        tag = "tag"
    ),
    "Test_HeaderTags_Colon_Leading": TestData(
        header = "header7",
        value = "val",
        config = ":header7",
        tag = None
    ),
    "Test_HeaderTags_Colon_Trailing": TestData(
        header = "header8",
        value = "val",
        config = "header8:",
        tag = None
    )
}

# I'm unclear on the "Python way" to do getters, LMK.
# I see using decorators? - https://stackoverflow.com/questions/2627002/whats-the-pythonic-way-to-use-getters-and-setters
def Header_Name(test_name):
    return header_tag_tests[test_name].header

def Header_Value(test_name):
    return header_tag_tests[test_name].value

def Config(test_name):
    return header_tag_tests[test_name].config

def Tag(test_name):
    return header_tag_tests[test_name].tag

def All_Configs():
    configs = []
    for k in header_tag_tests.keys():
        configs.append(header_tag_tests[k].config)
    return configs