ActiveRecord::Base.connection.execute <<-SQL
INSERT INTO foos (key, value) VALUES ("foo", "bar");
SQL

499.times do |i|
  ActiveRecord::Base.connection.execute <<-SQL
  INSERT INTO foos (key, value) VALUES ("#{i}", "");
  SQL
end
