# frozen_string_literal: true

class CreateUsers < ActiveRecord::Migration[7.1]
  def change
    create_table :users, id: :int do |t|
      ## Database authenticatable
      t.string :name
    end
  end
end
