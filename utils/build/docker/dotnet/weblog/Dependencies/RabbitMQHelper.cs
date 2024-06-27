using System;
using System.Text;
using System.Threading;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

public class RabbitMQHelper : IDisposable
{
    private IConnection _connection;
    private IModel _channel;

    public RabbitMQHelper()
    {
        IConnection? connection = null;
        IModel? channel = null;

        // RabbitMQ may not be available at startup
        while (connection == null || channel == null)
        {
            try
            {
                ConnectionFactory factory = new ConnectionFactory();
                factory.UserName = "guest";
                factory.Password = "guest";
                factory.HostName = "rabbitmq";
                factory.Port = 5672;

                connection = factory.CreateConnection();
                channel = connection.CreateModel();
            }
            catch (Exception e)
            {
                connection = null;
                channel = null;

                Log($"[rabbitmq] Failed to connect to the server \n{e}");
                Thread.Sleep(2000);
            }
        }

        _connection = connection;
        _channel = channel;
    }

    public void CreateQueue(string queue)
    {
        _channel.QueueDeclare(queue, durable: true, exclusive: false, autoDelete: false, arguments: null);
        Console.WriteLine($"[rabbitmq] Created queue {queue}");
    }

    public void ExchangeDeclare(string exchange, string type)
    {
        _channel.ExchangeDeclare(
            exchange,
            type,
            /*durable=*/true,
            /*autoDelete=*/false,
            null);

        Console.WriteLine($"[rabbitmq] Declare {exchange}:{type}");
    }

    public void QueueBind(string queue, string exchange, string routingKey)
    {
        _channel.QueueBind(
            queue,
            exchange,
            routingKey,
            null);

        Console.WriteLine($"[rabbitmq] Bind {queue} -> {exchange}:{routingKey}");
    }

    public void ExchangePublish(string exchange, string routingKey, string message)
    {
        _channel.BasicPublish(
            exchange,
            routingKey,
            null,
            Encoding.UTF8.GetBytes(message)
            );

        Console.WriteLine($"[rabbitmq] Exchange publish {exchange}:{routingKey} -> {message}");
    }

    public void DirectPublish(string routingKey, string message)
    {
        _channel.BasicPublish(
            $"",
            routingKey,
            null,
            Encoding.UTF8.GetBytes(message)
        );

        Console.WriteLine($"[rabbitmq] Direct publish {routingKey} -> {message}");
    }

    public void AddListener(string queue, Action<string> proc)
    {
        var consumer = new EventingBasicConsumer(_channel);
        consumer.Received += (channel, ea) =>
        {
            proc(Encoding.UTF8.GetString(ea.Body.ToArray()));
        };

        _channel.BasicConsume(queue, true, consumer);
    }

    public void Dispose()
    {
        _channel.Dispose();
        _connection.Dispose();
    }

    public void Log(string message)
    {
        Console.WriteLine($"{DateTime.Now} -> {message}");
    }
}