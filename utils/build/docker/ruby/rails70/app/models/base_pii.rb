class BasePii
  def initialize
    @test_value = 'should be redacted'
  end

  attr_reader :test_value
end
