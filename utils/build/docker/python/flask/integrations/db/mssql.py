try:
    import pyodbc
except ModuleNotFoundError:
    print("pyodbc not loaded")

database_mssql_loaded = 0
SERVER = "mssql"
DATABASE = "master"
USERNAME = "sa"
PASSWORD = "yourStrong(!)Password"


def executeMssqlOperation(
    operation,
):
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


def connect_db():
    connectionString = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;"
    conn = pyodbc.connect(connectionString)
    return conn


def createDatabase():
    print("CREATING MSSQL DATABASE!")

    sql_table = " CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL,age INT NOT NULL,PRIMARY KEY (ID));"
    sql_insert_1 = "insert into demo (id,name,age) values(1,'test',16);"
    sql_insert_2 = "insert into demo (id,name,age) values(2,'test2',17);"

    procedure = """ CREATE PROCEDURE helloworld 
         @Name VARCHAR(100) , @Test VARCHAR(100) 
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
    conn.commit()
    cursor.close()
    print(" MSSQL DATABASE CREATED")
    return "OK"


def select():
    sql = "SELECT * from demo where id=1 or id IN (3, 4);"
    _executeQuery(sql)
    return "OK"


def select_error():
    sql = "SELECT * from demosssss where id=1 or id=233333;"
    _executeQuery(sql)
    return "OK"


def update():
    sql = "update demo set age=22 where id=1;"
    _executeQuery(sql)
    return "OK"


def delete():
    sql = "delete from demo where id=2 or id=11111111;"
    _executeQuery(sql)
    return "OK"


def insert():
    sql = "insert into demo (id,name,age) values(3,'test3',163);"
    _executeQuery(sql)
    return "OK"


def procedure():
    _executeQuery("exec helloworld  @Name='param1', @Test= 'param2'")
    return "OK"


def _executeQuery(query):
    cursor = connect_db().cursor()
    cursor.execute(query)
    cursor.close()
