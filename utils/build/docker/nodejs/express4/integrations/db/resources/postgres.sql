DROP TABLE IF EXISTS demo;

CREATE TABLE demo(
    id INT NOT NULL,
    name VARCHAR (20) NOT NULL,
    age INT NOT NULL,
    PRIMARY KEY (ID)
);

insert into demo (id,name,age) values(1,'test',16);
insert into demo (id,name,age) values(2,'test2',17);


CREATE OR REPLACE PROCEDURE helloworld(id int, other varchar(10)) LANGUAGE plpgsql
 AS
 $$
 BEGIN
 raise info 'Hello World';
 END;
 $$;