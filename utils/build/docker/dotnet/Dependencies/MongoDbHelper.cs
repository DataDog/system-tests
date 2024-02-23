using MongoDB.Bson;
using MongoDB.Driver;

namespace weblog;

public class MongoDbHelper
{
    private IMongoClient _client;
    private readonly IMongoDatabase _database;

    public MongoDbHelper(string connectionString, string databaseName)
    {
        _client = new MongoClient(connectionString);
        _database = _client.GetDatabase(databaseName);
    }
    
    public BsonDocument Find(string collectionName, string json)
    {
        var collection = _database.GetCollection<BsonDocument>(collectionName);
        return collection.Find(json).FirstOrDefault();
    }
    
    public BsonDocument Find(string collectionName, BsonDocument filter)
    {
        var collection = _database.GetCollection<BsonDocument>(collectionName);
        return collection.Find(filter).FirstOrDefault();
    }
    
    public static BsonDocument CreateSimpleDocument(string key, string value)
    {
        return new BsonDocument(key, value);
    }
}