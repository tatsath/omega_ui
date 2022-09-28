import flask
import json
import logging
import os
import uuid
import redis

import dash
import dash.dependencies as dd
#import dash_auth
from dash import dcc, html, dash_table
# from dash import html
import dash.dash_table as dtb

import omega_ui.configuration as oc
import omega_ui.backend as ob
from dash.exceptions import PreventUpdate


debug_mode = False  # set False to deploy

root_directory = os.getcwd()
stylesheets = ['stylesheet.css']
jss = ['script.js']
static_route = '/static/'


app = dash.Dash(__name__, external_stylesheets=['static/stylesheet.css'])

#app = dash.Dash(__name__)
server = app.server
app.title = 'Omega - Backtest'
#app.scripts.config.serve_locally = False

# level_marks = ['Debug', 'Info', 'Warning', 'Error']
level_marks = {0: 'Debug', 1: 'Info', 2: 'Warning', 3: 'Error'}
num_marks = 4
 

left_column = html.Div([
    html.Div([
        html.Div('Symbols:', className='four columns'),
        dcc.Dropdown(
            id='symbols',
            options=[{'label': name, 'value': name} for name in ob.backtest.get_symbols()],
            multi=True,
            className='eight columns u-pull-right')
    ], className='row mb-10'),
    html.Div([
        html.Div('Module:', className='four columns'),
        dcc.Dropdown(
            id='module',
            options=[{'label': name, 'value': name} for name in oc.cfg['backtest']['modules'].split(',')],
            className='eight columns u-pull-right')
    ], className='row mb-10'),
    html.Div([
        html.Div('Strategy:', className='four columns'),
        dcc.Dropdown(id='strategy', options=[], className='eight columns u-pull-right')
    ], className='row mb-10'),
    html.Div(
        dash_table.DataTable(
            row_selectable=ob.cash_param(),
            # optional - sets the order of columns
            columns=[{"name": i, "id": i} for i in['Parameter', 'Value']],
            editable=True,
            id='params-table'
        ), className='row mb-10'),

    html.Div([
        html.Div('Notes:'),
        html.Textarea(id='notes-area', style={'width': '100%'})
    ], className='row', style={'vertical-align': 'bottom'}),
], className="three columns gray-block", style={'position': 'absolute', 'top': 0, 'bottom': '123px'})

center = html.Div([
    html.Div([
        html.Div([dcc.Graph(id='charts')]),
    ], id='graph-container', className='row',
        style={'position': 'absolute', 'top': '0px', 'bottom': '0px', 'left': '0px', 'right': '0px'})
], className='offset-by-three six columns gray-block', style={'position': 'absolute', 'top': 0,  'bottom': '9.2em'})

right_column = html.Div([
    html.Div(
        html.Div([
            html.Div([
                html.Div([
                    html.Button('Backtest', id='backtest-btn', n_clicks=0, style={'width': '34%', 'margin-left': 0, 'margin-right': '3%'}),
                    html.Button('Save', id='save-btn', n_clicks=0, style={'width': '30%', 'margin-left': 0, 'margin-right': '3%'}),
                    html.Button('Load', id='load-btn', n_clicks=0, style={'width': '30%', 'margin-left': 0, 'margin-right': 0}),
                ]),
                html.Div(id='status-area', style={
                    'margin-top': '10px',
                    'padding-left': '10px',
                    'border': '1px solid black',
                    'line-height': '40px',
                    'min-height': '40px',
                })
            ], className='gray-block mb-10'),
            html.Div(id='stat-block', className='block',
                    style={'position': 'absolute', 'top': '155px', 'bottom': '9.2em', 'left': '75.75%', 'right': 0}),
        ], className='twelve columns'), className='row'),
], className='offset-by-nine three columns')

bottom = html.Div([
    html.Div([
        html.Div('Logs:', className='one columns'),
        html.Div('Level:', className='one columns'),
        html.Div([
            dcc.RangeSlider(
                id='level-slider',
                marks=level_marks,
                min=0,
                max=num_marks-1,
                step=1,
                value=[0, num_marks-1],
            )
        ], className='five columns', style={'margin-top': '-0.5em', 'margin-left': '-1em', })
    ], className='row mb-10'),
    html.Iframe(id='log-frame', style={
        'width': '100%',
        'background-color': 'white',
        'border': '1px solid black',
        'min-height': '20em',
        'margin-bottom': '-1em'
    }, className='row'),
], className='gray-block')

app.layout = html.Div([
    html.Div(
        html.Div(html.H1('Omega'), className='gray-block2 mb-10'),
        style={'position': 'absolute', 'right': '1em', 'width': '99%'}),
    html.Div([
        html.Div([
            left_column, center, right_column
        ], className='row', style={'position': 'absolute', 'bottom': '18em', 'top': '7em', 'right': '1em', 'width': '99%'}),
        html.Div(
            bottom
            , className='row', style={'position': 'absolute', 'bottom': '0.5em', 'right': '1em', 'width': '99%'})
    ]),
    html.Div(id='intermediate-value', style={'display': 'none'}),
    html.Div(id='intermediate-params', style={'display': 'none'}),
    html.Div(id='intermediate-status', style={'display': 'none'}),
    html.Div(id='level-log', contentEditable='True', style={'display': 'none'}),
    dcc.Input(id='log-uid', type='text', style={'display': 'none'})
])


for stylesheet in stylesheets:
    app.css.append_css({"external_url": "/static/{}".format(stylesheet)})

app.scripts.append_script({"external_url": "//code.jquery.com/jquery-1.4.2.min.js"})
app.scripts.append_script({"external_url": "//cdnjs.cloudflare.com/ajax/libs/socket.io/1.3.5/socket.io.min.js"})


for js in jss:
    app.scripts.append_script({"external_url": "/static/{}".format(js)})


@app.server.route('{}<file>'.format(static_route))
def serve_file(file):
    if file not in stylesheets and file not in jss:
        raise Exception('"{}" is excluded from the allowed static css files'.format(file))
    static_directory = os.path.join(root_directory, 'static')
    return flask.send_from_directory(static_directory, file)

@app.callback(dd.Output('strategy', 'options'), [dd.Input('module', 'value')])
def update_strategy_list(module_name):
    data = ob.test_list(module_name)
    return [{'label': name, 'value': name} for name in data]


@app.callback(dd.Output('params-table', 'columns'), [dd.Input('module', 'value'), dd.Input('strategy', 'value'), dd.Input('symbols', 'value')])
def update_params_list(module_name, strategy_name, symbol):
    return ob.params_list(module_name, strategy_name, symbol)


@app.callback(dd.Output('strategy', 'value'), [dd.Input('strategy', 'options')])
def update_strategy_value(options):
    if len(options):
        return options[0]['value']
    return ''


@app.callback(dd.Output('status-area', 'children'),
              [
                  dd.Input('backtest-btn', 'n_clicks'),
                  dd.Input('intermediate-params', 'children'),
                  dd.Input('intermediate-value', 'children')
              ])
def update_status_area(n_clicks, packed_params, result):
    if result:
        return 'Done!'
    if n_clicks == 0:
        return ''
    module, strategy, symbol = None, None, None
    try:
        params = json.loads(packed_params)
        if 'module_i' in params:
            module = params['module_i']
        if 'strategy_i' in params:
            strategy = None if params['strategy_i'] == '' else params['strategy_i']
        if 'symbols_i' in params:
            symbol = params['symbols_i']
    except:
        pass
    to_provide = []
    if module is None:
        to_provide.append('module')
    if strategy is None:
        to_provide.append('strategy')
    if symbol is None:
        to_provide.append('symbol')
    if len(to_provide):
        return 'Please provide a value for: {}!'.format(', '.join(to_provide))

    return 'Backtesting...'


@app.callback(dd.Output('log-uid', 'value'), [dd.Input('symbols', 'options')])
def create_uid(m):
    return uuid.uuid4().hex


@app.callback(dd.Output('intermediate-value', 'children'),
              [dd.Input('intermediate-params', 'children'), dd.Input('log-uid', 'value')])
def on_click_backtest_to_intermediate(json_packed, uid):
    try:
        unpacked = json.loads(json_packed)
        module = unpacked['module_i']
        strategy = unpacked['strategy_i']
        symbols = unpacked['symbols_i']
        params = unpacked['table_params']
        #params = {}
        if module is None or strategy is None or symbols is None:
            return []
        return ob.create_ts(uid, module, strategy, symbols, params)
    except json.decoder.JSONDecodeError:
        # Ignoring this error (this is happening when inputting values in Module/Strategy boxes)
        return []


@app.callback(dd.Output('backtest-btn', 'n_clicks'),
              [
                  dd.Input('module', 'value'),
                  dd.Input('strategy', 'value'),
                  dd.Input('symbols', 'value'),
                  dd.Input('params-table', 'columns')
              ])
def reset_button(*args):
    return 0


@app.callback(dd.Output('intermediate-params', 'children'),
              [
                  dd.Input('backtest-btn', 'n_clicks'),
                  dd.Input('module', 'value'),
                  dd.Input('strategy', 'value'),
                  dd.Input('symbols', 'value'),
                  dd.Input('params-table', 'columns')
              ])
def update_params(n_clicks, module, strategy, symbol, rows):
    if n_clicks == 0:
        return ''
    params = {'module_i': module, 'strategy_i': strategy, 'symbols_i': symbol}
    table_params = {}
    for row in rows:
        table_params[row['name']] = str(row['id'])
    params['table_params'] = table_params
    return json.dumps(params)


@app.callback(dd.Output('charts', 'figure'),
              [dd.Input('intermediate-value', 'children'), dd.Input('log-uid', 'value')], prevent_initial_call=True)
def on_intermediate_to_chart(children, uid):
    # r = redis.StrictRedis(oc.cfg['default']['redis'], 6379, db=0)
    # size = r.get(uid + 'size')
    # w, h = size.decode('utf8').split(',')
    # return ob.extract_figure(children, w, h)
    if len(children) == 0:
        return dash.no_update
    return ob.extract_figure(children)


@app.callback(
    dash.dependencies.Output('level-log', 'children'),
    [dash.dependencies.Input('level-slider', 'value')])
def level_output(value):
    begin, end = value
    res = []
    for i in range(begin, end+1):
        res.append(level_marks[i].upper())
    return ','.join(res)


@app.callback(dd.Output('stat-block', 'children'), [dd.Input('intermediate-value', 'children')])
def on_intermediate_to_stat(children):
    statistic = ob.extract_statistic(children)
    ht = []
    for section in statistic:
        ht.append(html.Div(html.B(section, style={'font-size': '1.1em', 'line-height': '1.5m'}), className='row'))
        for stat in statistic[section]:
            ht.append(
                html.Div([
                    html.Div(stat, className='u-pull-left'),
                    html.Div(html.B(statistic[section].get(stat)), className='u-pull-right')
                ], className='row'))
        ht.append(html.Div(style={'border': '1px solid #999', 'margin': '10px 10px 5px'}))
    return html.Div(html.Div(ht[:-1], className='twelve columns', style={'line-height': '1.4em'}), className='row')


# if not debug_mode:
#     auth = dash_auth.BasicAuth(
#         app,
#         ob.get_users()
#     )


# Before running the app, please run the following 'python socket_logged.py flask run'
if __name__ == '__main__':
    logger = logging.getLogger('werkzeug')
    handler = logging.FileHandler(ob.LogFileCreator.werkzeug_log_file_name())
    logger.addHandler(handler)
    # app.run_server(host='localhost', debug=debug_mode)
    app.run_server(debug=True, port=8086)
