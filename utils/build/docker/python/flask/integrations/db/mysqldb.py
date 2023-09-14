try:
    import pymysql
except ModuleNotFoundError:
    print("pmysql not loaded")

database_mysql_loaded = 0


def executeMysqlOperation(operation,):
    global database_mysql_loaded
    if database_mysql_loaded == 0:
        createDatabae()
    database_mysql_loaded = 1
    print(f"Executing postgres {operation} operation")
    if operation == "select":
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


def connect_db():
    return pymysql.connect(
        user="mysqldb",
        password="mysqldb",
        database="world",
        autocommit=True,
        charset="utf8mb4",
        host="mysqldb",
        cursorclass=pymysql.cursors.DictCursor,
    )


def createDatabae():
    print("CREATING MYSQL DATABASE")
    sql_table = " CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL, age INT NOT NULL, PRIMARY KEY (ID));"
    sql_insert_1 = "insert into demo (id,name,age) values(1,'test',16);"
    sql_insert_2 = "insert into demo (id,name,age) values(2,'test2',17);"

    procedure = """CREATE PROCEDURE test_procedure(IN test_id INT) 
           BEGIN 
           SELECT demo.id, demo.name,demo.age 
           FROM demo 
           WHERE demo.id = test_id; 
           END """

    cursor = connect_db().cursor()
    cursor.execute(sql_table)
    cursor.execute(sql_insert_1)
    cursor.execute(sql_insert_2)
    cursor.execute(procedure)
    cursor.close()
    return "OK"


def select():
    sql = "SELECT * from demo;"
    _executeQuery(sql)
    return "OK"


def select_error():
    sql = "SELECT * from demosssss;"
    _executeQuery(sql)
    return "OK"


def update():
    sql = "update demo set age=22 where id=1;"
    _executeQuery(sql)
    return "OK"


def delete():
    sql = "delete from demo where id=2;"
    _executeQuery(sql)
    return "OK"


def insert():
    sql = "insert into demo (id,name,age) values(3,'test3',163);"
    _executeQuery(sql)
    return "OK"


def procedure():
    _executeQuery("call test_procedure(1)")
    return "OK"


def _executeQuery(sql):
    cursor = connect_db().cursor()
    cursor.execute(sql)
    cursor.close()
