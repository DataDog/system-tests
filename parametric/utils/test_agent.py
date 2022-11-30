def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span
