package com.datadoghq.system_tests.springboot;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class CollectionFactory {

    public static Object getCollection(int length, String type) {
        switch (type) {
            case "array":
                return getArray(length);
            case "list":
                return getList(length);
            case "hash":
                return getDictionary(length);
            default:
                return getArray(length);
        }
    }

    private static int[] getArray(int length) {
        int[] array = new int[length];
        for (int i = 0; i < length; i++) {
            array[i] = i;
        }
        return array;
    }

    private static List<Integer> getList(int length) {
        List<Integer> list = new ArrayList<>(length);
        for (int i = 0; i < length; i++) {
            list.add(i);
        }
        return list;
    }

    private static Map<Integer, Integer> getDictionary(int length) {
        Map<Integer, Integer> dictionary = new HashMap<>(length);
        for (int i = 0; i < length; i++) {
            dictionary.put(i, i);
        }
        return dictionary;
    }

    public static void main(String[] args) {
        // Test cases
        System.out.println(java.util.Arrays.toString((int[]) CollectionFactory.getCollection(5, "array")));
        System.out.println(CollectionFactory.getCollection(5, "list"));
        System.out.println(CollectionFactory.getCollection(5, "hash"));
    }
}
