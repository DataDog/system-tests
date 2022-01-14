class CreateTableFoos < ActiveRecord::Migration[5.2]
  def change
    create_table :foos do |t|
      t.string :key
      t.string :value
    end

    add_index :foos, :key
  end
end
