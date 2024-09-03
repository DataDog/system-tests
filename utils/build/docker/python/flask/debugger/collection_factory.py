class CollectionFactory:
    @staticmethod
    def get_collection(length, collection_type):
        if collection_type == "array":
            return CollectionFactory.get_array(length)
        elif collection_type == "list":
            return CollectionFactory.get_list(length)
        elif collection_type == "hash":
            return CollectionFactory.get_dictionary(length)
        else:
            return CollectionFactory.get_array(length)

    @staticmethod
    def get_array(length):
        return [i for i in range(length)]

    @staticmethod
    def get_list(length):
        return [i for i in range(length)]

    @staticmethod
    def get_dictionary(length):
        return {i: i for i in range(length)}
