def get_span(test_agent):
    traces = test_agent.wait_for_num_traces(num=1)
    span = traces[0][0]
    return span
