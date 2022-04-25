class _Xfails:
    def __init__(self):
        self.methods = {}
        self.classes = set()

    def add_xfailed_class(self, klass):
        self.classes.add(klass)

    def add_xfailed_method(self, method):
        self.methods[method] = []

    def is_xfail_method(self, method):
        return method in self.methods

    def is_xfail_class(self, klass):
        return klass in self.classes

    def add_validation_from_method(self, method, validation):
        """ The validation is xfail because the calling method is xfail"""
        self.methods[method].append(validation)

    def add_validation_from_class(self, klass, method, validation):
        """ The validation is xfail because the parent class of calling method is xfail"""
        assert self.is_xfail_class(klass)
        if not self.is_xfail_method(method):
            self.add_xfailed_method(method)
        self.add_validation_from_method(method, validation)


xfails = _Xfails()
