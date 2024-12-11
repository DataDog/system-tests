CREATE TABLE demo(id INT NOT NULL, name VARCHAR (20) NOT NULL,age INT NOT NULL,PRIMARY KEY (ID));
insert into demo (id,name,age) values(1,'testzz',16);
insert into demo (id,name,age) values(2,'test2',17);
CREATE PROCEDURE test_procedure(IN test_id INT,IN other VARCHAR(20))
           BEGIN
          SELECT demo.id, demo.name,demo.age
          FROM demo
           WHERE demo.id = test_id;
           END