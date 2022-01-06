class _Xfails:
    def __init__(self):
        self.methods = {}
        self.classes = {}

    def add_xfailed_class(self, klass):
        self.classes[klass] = []

    def add_xfailed_method(self, method):
        self.methods[method] = []

    def is_xfail_method(self, method):
        return method in self.methods

    def is_xfail_class(self, klass):
        return klass in self.classes

    def add_validation_from_method(self, method, validation):
        """ The validation is xfail because the calling method is xfail"""
        self.methods[method].append(validation)

    def add_validation_from_class(self, klass, validation):
        """ The validation is xfail because the parent class of calling method is xfail"""
        self.classes[klass].append(validation)


xfails = _Xfails()
