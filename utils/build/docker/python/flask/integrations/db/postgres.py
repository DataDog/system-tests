import psycopg2

POSTGRES_CONFIG = dict(
    host="postgres",
    port="5433",
    user="system_tests_user",
    password="system_tests",
    dbname="system_tests_dbname",
)


def executePostgresOperation(operation):
    print(f"Executing postgres {operation} operation")
    if operation == "init":
        createDatabase()
    elif operation == "select":
        select()
    elif operation == "select_error":
        select_error()
    elif operation == "update":
        update()
    elif operation == "delete":
        delete()
    elif operation == "insert":
        insert()
    elif operation == "procedure":
        procedure()
    else:
        print(f"Operation {operation} doesn't exist")


def createDatabase():
    print("CREATING POSTGRES DATABASE")
    sql = "CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL, age INT NOT NULL, PRIMARY KEY (ID));"
    sql = sql + "insert into demo (id,name,age) values(1,'test',16);"
    sql = sql + "insert into demo (id,name,age) values(2,'test2',17);"

    procedure = "CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10)) LANGUAGE plpgsql "
    procedure = procedure + " AS "
    procedure = procedure + " $$ "
    procedure = procedure + " BEGIN "
    procedure = procedure + " raise info 'Hello World'; "
    procedure = procedure + " END; "
    procedure = procedure + " $$;"

    sql = sql + procedure

    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)
    postgres_db.commit()
    cursor.close()
    postgres_db.close()
    return "OK"


def select():
    sql = "SELECT * from demo where id=1 or id IN (3, 4)"
    _executeQuery(sql)
    return "OK"


def select_error():
    sql = "SELECT * from demosssssssss where id=1 or id=233333"
    _executeQuery(sql)
    return "OK"


def update():
    sql = "update demo set age=22 where name like '%tes%'"
    _executeQuery(sql)
    return "OK"


def insert():
    sql = "insert into demo (id,name,age) values(3,'test3',163)"
    _executeQuery(sql)
    return "OK"


def delete():
    sql = "delete from demo where id=2 or id=11111111"
    _executeQuery(sql)
    return "OK"


def procedure():
    sql = "call helloworld(1,'test')"
    _executeQuery(sql)
    return "OK"


def _executeQuery(sql):
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)
    cursor.close()
    postgres_db.close()
