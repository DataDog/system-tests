from utils import context
from utils.interfaces._core import BaseValidation

context.execute_warmups = lambda *args, **kwargs: None


class Test_Main:
    """ test message collectors """

    def test_message_in_method(self):
        """ Test magic message collector """

        assert BaseValidation("Inline message").message == "Inline message"
        assert BaseValidation().message == "Test magic message collector", repr(BaseValidation().message)

    def test_message_in_class(self):
        # DO NOT set a doc string

        assert BaseValidation("Inline message").message == "Inline message"
        assert BaseValidation().message == "test message collectors"


class Test_NoDocstring:
    def test_main(self):
        try:
            BaseValidation()
        except Exception as e:
            assert str(e) == "Please set a message for test_main"
