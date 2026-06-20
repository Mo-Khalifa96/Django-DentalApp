import inspect
#Helper function to render response details on assertion error
def render_error(response):
    print('\n\n'+'='*100)
    print('Test name:', inspect.stack()[1].function)
    print('status code:', response.status_code)
    print('response data:', response.data)
    print('='*100+'\n\n')
