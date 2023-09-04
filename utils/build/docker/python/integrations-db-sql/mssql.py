import pyodbc

database_loaded = 0
SERVER = "mssql"
DATABASE = "master"
USERNAME = "sa"
PASSWORD = "yourStrong(!)Password"


def executeMssqlOperation(operation,):
    global database_loaded
    if database_loaded == 0:
        createDatabae()
    database_loaded = 1
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
    connectionString = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}"
    )
    conn = pyodbc.connect(connectionString)
    return conn


def createDatabae():
    print("CREATING MSSQL DATABASE")

    sql_table = " CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL,age INT NOT NULL,PRIMARY KEY (ID));"
    sql_insert_1 = "insert into demo (id,name,age) values(1,'test',16);"
    sql_insert_2 = "insert into demo (id,name,age) values(2,'test2',17);"

    procedure = """ CREATE PROCEDURE helloworld 
         AS 
         BEGIN 
         SET NOCOUNT ON 
         SELECT id from demo where id=1
    END  """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(sql_table)
    conn.commit()

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
    _executeQuery("helloworld")
    return "OK"


def _executeQuery(query):
    cursor = connect_db().cursor()
    cursor.execute(query)
    cursor.close()
