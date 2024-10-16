package com.datadoghq.system_tests.springboot;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class ExpressionTestStruct {
    public int IntValue = 1;
    public double DoubleValue = 1.1;
    public String StringValue = "one";
    public boolean BoolValue = true;

    public List<String> Collection;
    public Map<String, Integer> Dictionary;

    public ExpressionTestStruct() {
        Collection = new ArrayList<String>();
        Collection.add("one");
        Collection.add("two");
        Collection.add("three");

        Dictionary = new HashMap<String, Integer>();
        Dictionary.put("one", 1);
        Dictionary.put("two", 2);
        Dictionary.put("three", 3);
        Dictionary.put("four", 4);
    }
}
