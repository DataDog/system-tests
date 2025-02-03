using System;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace weblog.Models.Debugger
{
    public static class CollectionFactory
    {
        public static Task<ICollection> GetCollection( int length, string type)
        {
            switch (type)
            {
                case "array":
                    return Task.FromResult<ICollection>(GetArray(length));
                case "list":
                    return Task.FromResult<ICollection>(GetList(length));
                case "hash":
                    return Task.FromResult<ICollection>(GetDictionary(length));
                default:
                    return Task.FromResult<ICollection>(GetArray(length));
            }
        }

        private static int[] GetArray(int length)
        {
            var array = new int[length];
            for (int i = 0; i < length; i++)
            {
                array[i] = i;
            }

            return array;
        }

        private static List<int> GetList(int length)
        {
            var list = new List<int>(length);
            for (int i = 0; i < length; i++)
            {
                list.Add(i);
            }

            return list;
        }

        public static Dictionary<int, int> GetDictionary(int length)
        {
            var dictionary = new Dictionary<int, int>(length);
            for (int i = 0; i < length; i++)
            {
                dictionary.Add(i, i);
            }

            return dictionary;
        }
    }
}
