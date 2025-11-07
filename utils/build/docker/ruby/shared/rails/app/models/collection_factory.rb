class CollectionFactory
  def get_collection(length, type)
    case type
    when 'array', 'list'
      get_array(length)
    when 'hash'
      get_hash(length)
    else
      get_array(length)
    end
  end

  def get_array(length)
    0.upto(length-1).to_a
  end

  def get_hash(length)
    0.upto(length-1).map do |i|
      [i, i]
    end.to_h
  end
end
