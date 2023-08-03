# This file should contain all the record creation needed to seed the database with its default values.
# The data can then be loaded with the bin/rails db:seed command (or created alongside the database with db:setup).
#
# Examples:
#
#   movies = Movie.create([{ name: "Star Wars" }, { name: "Lord of the Rings" }])
#   Character.create(name: "Luke", movie: movies.first)

User.delete_all
User.create!(:id => 'social-security-id', :username => 'test', :email => 'testuser@ddog.com', :password => '1234', :password_confirmation => '1234')
User.create!(:id => '591dc126-8431-4d0f-9509-b23318d3dce4', :username => 'testuuid', :email => 'testuseruuid@ddog.com', :password => '1234', :password_confirmation => '1234')
