from operator import itemgetter

import dash
import dash_core_components as dcc
import dash_html_components as html
import flask
import dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import boto3
from boto3.dynamodb.conditions import Key

from styles import *


admin_pass = "test"
session = boto3.Session(profile_name="skill_matrix")

dynamodb = session.resource('dynamodb')
table = dynamodb.Table('skill_matrix')

### Query Functions ###
def dynamo_query(table, category):
    '''This function queries a pre-authenticated DynamoDB table to return all results that match a specific category.'''
    return table.query(
        KeyConditionExpression=Key('category').eq(category),
        Select='ALL_ATTRIBUTES',
        ConsistentRead=False
    )

def begins_dynamo_query(table, category, key):
    '''This function queries a pre-authenticated DynamoDB table to return all results that match a specific category and whose sort key begins with a supplied key string.'''
    return table.query(
        KeyConditionExpression=Key('category').eq(category) & Key('key').begins_with(key),
        Select='ALL_ATTRIBUTES',
        ConsistentRead=False
    )

skill = dynamo_query(table=table, category='skill')   
skill_list = [i['skill'] for i in skill['Items']]
state_list = [State('input_user', 'value')] + [State(i+'_ability', 'value') for i in skill_list] + [State(i+'_interest', 'values') for i in skill_list]

server = flask.Flask(__name__)

external_css = [
    "https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css",
    "https://fonts.googleapis.com/css?family=Raleway:400,400i,700,700i",
]

app = dash.Dash(
    name=__name__,
    server=server,
    external_stylesheets=external_css,
)

app.config['suppress_callback_exceptions']=True

app.layout = html.Div([
    html.Div([
        html.H2('SKILL MATRIX',style=banner_h2_style,id='main_banner'),
        html.Img(src='https://www.edfenergy.com/profiles/spire_profile/themes/custom/spire/logo.png',style=banner_img_style),
        ],style=banner_style),
    html.Div([
        dcc.Tabs(id='skill_matrix_tabs', value='skill_input', children=[
            dcc.Tab(label='INPUT FORM', value='skill_input', style=tab_style, selected_style=tab_selected_style),
            dcc.Tab(label='SKILL VIEW', value='skill_view', style=tab_style, selected_style=tab_selected_style),
            dcc.Tab(label='BUDDY MATCHER', value='buddy_list', style=tab_style, selected_style=tab_selected_style),
            dcc.Tab(label='ADMIN PORTAL', value='admin_portal', style=tab_style, selected_style=tab_selected_style),
        ])
    ],className='tabs'),
    html.Div(id='tabs-content'),
    html.Div(id='new_user_hidden', style={'display':'none'}),
    html.Div(id='new_skill_hidden', style={'display':'none'}),
    html.Div(id='remove_user_hidden', style={'display':'none'}),
    html.Div(id='remove_skill_hidden', style={'display':'none'})
],style=body_style)

### This callback provides the main content to the web app ###
@app.callback(Output('tabs-content', 'children'),
              [Input('skill_matrix_tabs', 'value')])
def render_content(tab):
    ### SKILL INPUT TAB ###
    if tab == 'skill_input':
        people = dynamo_query(table=table, category='people') 
        team_list = list(set([i['team'] for i in people['Items']]))
        user_list = [i['name'] for i in people['Items'] if i['team'] == team_list[0]]
        
        
        return html.Div([
            html.Div([
                html.Div([
                    html.B('Team :',style=label_style),
                    dcc.Dropdown(id='input_team',options=[{'label':i, 'value':i} for i in team_list],value=team_list[0],style=team_dropdown_style)
                ],style=block_style),
                html.Div([
                    html.B('User :',style=label_style),
                    dcc.Dropdown(id='input_user',options=[{'label':i, 'value':i} for i in user_list],value=user_list[0],style=user_dropdown_style),
                ],style=button_block_style),
                html.Div([
                    html.Button('Load User',id='skills_button',style=load_button_style)
                ],style=button_block_style),
            ],className='user',style={'height':'90px'}),
            html.Div([
                html.B('SKILL',style=divider_style_1),
                html.B('ABILITY',style=divider_style_2),
                html.B('INTEREST',style=divider_style_3)
            ],style=tab_title_style),
            html.Div(id='skill_box',className='skills'),
            html.Div(style=tab_footer_style)
        ])
    
    ### SKILL VIEW TAB ###
    elif tab == 'skill_view':
        
        people_query = dynamo_query(table=table, category='people')
        team_list = list(set([i['team'] for i in people_query['Items']]))
        return html.Div([
            html.Div([
                html.Div([
                    html.B('Team :',style=label_style),
                    dcc.Dropdown(id='tv_team_dd',options=[{'label':i, 'value':i} for i in ['Skill View'] + team_list],value=team_list[0],style=dropdown_style),
                    dcc.Checklist(id='tv_skill_select',options=[{'label':i, 'value':i} for i in skill_list],value=[i for i in skill_list],labelStyle=checklist_style,style={}),
                    dcc.Checklist(id='tv_interest_select',options=[{'label':i, 'value':i} for i in ['Student','Teacher']],value=[],labelStyle=checklist_style,style={})
                ],style=block_style),
                html.Div([
                    html.Button('Update View',id='tv_update_button',style=update_button_style)
                ],style=button_block_style)
            ],style=block_style),
            html.Div(style=tab_title_style),
            html.Div(id='tv_skill_map'),
            html.Div(style=tab_footer_style),
        ])
    ### BUDDY LIST TAB ###
    elif tab == 'buddy_list':
        competency_query = dynamo_query(table=table, category='competency')
        students = [{'name':i['name'],'skill':i['skill'],'ability':i['ability']} for i in competency_query['Items'] if i['student'] == 'true']
        matches = []
        for student in students:
            sub_matches = [{'key':' - '.join(sorted([i['name'],student['name']])),'teacher_name':i['name'],'skill':i['skill'],'teacher_ability':int(i['ability']),'student_name':student['name'],'student_ability':int(student['ability'])} for i in competency_query['Items'] if i['teacher'] == 'true' and i['skill'] == student['skill'] and i['ability'] >= student['ability'] and i['name'] != student['name']]
            matches = matches + sub_matches
        
        unique_matches = list(set([i['key'] for i in matches]))
        occurances = [i['key'] for i in matches]
        match_counts = [{'Match':i,'Matched Skill Count':occurances.count(i),'Skills':', '.join([j['skill'] for j in matches if j['key'] == i])} for i in unique_matches]
        match_counts = sorted(match_counts, key=itemgetter('Matched Skill Count'),reverse=True)
        
        return html.Div([
            html.Div(style=tab_title_style),
            dash_table.DataTable(
                id='Buddy Table',
                columns = [{'name':i, 'id':i} for i in ['Match','Matched Skill Count','Skills']],
                data = match_counts,
                style_cell={'textAlign': 'left','font':'Raleway'},
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': 'rgb(248, 248, 248)',
                    }
                ]
            ),
            html.Div(style=tab_footer_style)
        ])
    ### ADMIN PORTAL TAB ###
    elif tab == 'admin_portal':
        return html.Div([
            html.Div([
                html.B('Admin Password :',style=label_style),
                dcc.Input(id='admin_pass', value='', type='password',style={'fontSize':'18'}),
                html.Button('Submit',id='pass_submit',style=admin_button_style)
            ],style=admin_row_style),
            html.Div(style=tab_title_style),
            html.Div(id='hidden_content'),
            html.Div(style=tab_footer_style),
        ])

### SKILL INPUT TAB ### This callback updates the user list when the team dropdown is changed ###    
@app.callback(
    Output('input_user', 'options'),
    [Input('input_team', 'value')])
def update_users(value):
    people = dynamo_query(table=table, category='people') 
    return [{'label':i['name'], 'value':i['name']} for i in people['Items'] if i['team'] == value]

### SKILL INPUT TAB ### This callback updates skill list and input controls ###      
@app.callback(
    Output('skill_box', 'children'),
    [Input('skills_button', 'n_clicks')],
    [State('input_user','value')])
def update_skill_values(n_clicks,user):
    if n_clicks is not None:
        competency = begins_dynamo_query(table=table, category='competency', key=user)
        
        competency_dict = {comp['skill']:comp for comp in competency['Items']}
        
        div_list = []
        for section in skill_list:
            section_interest = []
            #Look for student property
            try:
                if competency_dict[section]['student'] == 'true': section_interest.append('STU')
            except:
                pass
            
            #Look for teacher property
            try:
                if competency_dict[section]['teacher'] == 'true' : section_interest.append('TCH')
            except:
                pass
            
            #Look for ability property - replace with 0 if not there
            try:
                section_ability = competency_dict[section]['ability']
            except:
                section_ability = 0
                
            div = html.Div([
                html.B(section,style=skill_row_style),
                dcc.Dropdown(
                    id=section+'_ability',
                    options=[{'label': 'None', 'value': 0},{'label': 'Beginner', 'value': 1},{'label': 'Intermediate', 'value':2},{'label': 'Advanced', 'value':3}],
                    value=section_ability,
                    style=skill_dropdown_style
                ),
                dcc.Checklist(
                    id=section+'_interest',
                    options=[{'label': 'Student', 'value': 'STU'},{'label': 'Teacher', 'value': 'TCH'}],
                    value=section_interest,
                    labelStyle=block_style,
                    style=skill_checklist_style
                )
            ])
            div_list.append(div)
        
        button_response = html.Div([html.Button('Submit',id='submit_button',style=update_button_style),
                                    html.B('',id='submit_response',style=skill_response_style)
                                    ])
        
        div_list.append(button_response)
    
        return div_list
    
## SKILL INPUT TAB ### This callback updates DynamoDB when a user has finsihed updating their skills ###    
@app.callback(
    Output('submit_response', 'children'),
    [Input('submit_button', 'n_clicks')],
    state_list)
def update_output(n_clicks,user_drop,*Stuff):
    if n_clicks is not None:
        ability_input = Stuff[:len(skill_list)]
        interest_input = Stuff[len(skill_list):]
        interest_input = [x if x is not None else '' for x in interest_input]
        
        dict_input_list = []
        for i in range(len(skill_list)):
            if 'STU' in interest_input[i]: student_input = 'true' 
            else : student_input = 'false'
            
            if 'TCH' in interest_input[i] : teach_input = 'true'
            else : teach_input = 'false'
            
            dict_input = {'category':'competency','key':user_drop + '-' + skill_list[i],'skill':skill_list[i],'name':user_drop,'ability':ability_input[i],'student':student_input,'teacher':teach_input}
            dict_input_list.append(dict_input)
        
        with table.batch_writer() as batch:
            for record in dict_input_list:
                batch.put_item(Item=record)
                
        return 'Skills updated for {}'.format(user_drop)

### SKILL VIEW TAB ### This callback updates the skill view graph ### 
@app.callback(
    Output('tv_skill_map', 'children'), #figure
    [Input('tv_update_button', 'n_clicks')],
    [State('tv_skill_select','value'),State('tv_interest_select','value'),State('tv_team_dd','value')])
def update_skill_map(n_clicks,select_skills,select_interests,select_team):
    competency_query = dynamo_query(table=table, category='competency')
    people_query = dynamo_query(table=table, category='people')
    
    if select_team == 'Skill View':
        team_user_list = list(set([i['name'] for i in competency_query['Items'] if i['skill'] in select_skills and i['ability'] > 0]))
    else :
        team_user_list = [i['name'] for i in people_query['Items'] if i['team'] == select_team]
        
    competency_dict = {user : {i['skill']:i['ability'] for i in competency_query['Items'] if i['name'] == user} for user in team_user_list}
    
    z = []
    hover_z = []
    for user in team_user_list:
        line = []
        hover_line = []
        for skill in select_skills:
            try:
                val = int(competency_dict[user][skill])
            except:
                val = 0
            line.append(val)
            hover_text = user + ' : ' + skill + '<br>Ability : ' + competency_replace[val]
            hover_line.append(hover_text)
        z.append(line)
        hover_z.append(hover_line)
    
    if len(select_interests) == 0:
        legend_width = 0
    else:
        legend_width = 150
        
    table_width = str(skill_view_dimensions['table_right'] + skill_view_dimensions['table_left'] + skill_view_dimensions['table_cell'] * len(select_skills) + legend_width)
    table_height = str(skill_view_dimensions['table_top'] + skill_view_dimensions['table_bottom'] + skill_view_dimensions['table_cell'] * len(team_user_list))
    skill_map = go.Heatmap(z=z, x=select_skills, y=team_user_list, text=hover_z, xgap=5, ygap=5, hoverinfo='text', colorscale=heat_mapper, showscale=False)
    traces = [skill_map]
    
    for interested in ['Teacher','Student']: 
        if interested in select_interests:
            interest_x = [i['skill'] for i in competency_query['Items'] if i[interested.lower()] == 'true' and i['name'] in team_user_list and i['skill'] in select_skills]
            interest_y = [i['name'] for i in competency_query['Items'] if i[interested.lower()] == 'true' and i['name'] in team_user_list and i['skill'] in select_skills]
            
            interest_symbols = go.Scatter(name=interested,x=interest_x, y=interest_y, mode='markers',hoverinfo='none',showlegend=True,marker={'color':'#AA3939','symbol': interest_marker_dict[interested], 'size': interest_size_dict[interested],'line':{'width':2.5}})
            traces.append(interest_symbols)                                                                                                                                                                                                                                         
                                                                                                                      
    return dcc.Graph(figure={'data':traces,
                             'layout':{'height':table_height,
                                       'width':table_width,
                                       'margin':{'l': skill_view_dimensions['table_left'], 'b': skill_view_dimensions['table_bottom'], 't': skill_view_dimensions['table_top'], 'r': skill_view_dimensions['table_right'] + legend_width},
                                       'xaxis':{'side':'top'},'yaxis':{}}})

   
### ADMIN PORTAL TAB ### This callback updates the hidden admin section is a user submits the correct password ### 
@app.callback(
    Output('hidden_content', 'children'), #figure
    [Input('pass_submit', 'n_clicks')],
    [State('admin_pass','value')])
def update_admin_portal(n_clicks,password):
    if password == admin_pass and n_clicks <= 5:
        people = dynamo_query(table=table, category='people')
        team_list = list(set([i['team'] for i in people['Items']]))
        user_list = [i['name'] for i in people['Items']]
        skill = dynamo_query(table=table, category='skill')   
        skill_list = [i['skill'] for i in skill['Items']]
        
        
        
        return [html.Div([html.Div([html.Div([html.B('Add New User',style={'fontSize':'24'})]), 
                                    html.Div([html.B('User Name :',style={'fontSize':'16'})]),
                                    html.Div([dcc.Input(id='new_user', value='', type='text',style=admin_text_style)]),
                                    html.Div([html.B('Team :',style={'fontSize':'16'})]),
                                    html.Div([dcc.Dropdown(id='new_user_team',options=[{'label':i, 'value':i} for i in team_list],value=team_list[0],style=admin_text_style)],style={}),
                                    html.Div([dcc.ConfirmDialogProvider(html.Button('Add New User',style=admin_user_button_style),id='new_user_submit',message='Are you sure you wish to add this new user?')])
                                    ],style=admin_col_style),
                          html.Div([html.Div([html.B('Remove User',style={'fontSize':'24'})]),
                                    html.Div([html.B('User :',style={'fontSize':'16'})]),
                                    html.Div([dcc.Dropdown(id='remove_user_user',options=[{'label':i, 'value':i} for i in user_list],value=user_list[0],style=admin_text_style)],style={}),
                                    html.Div([html.B('Team :',style={'fontSize':'16'})],style={'marginTop': 20}),
                                    html.Div([dcc.Dropdown(id='remove_user_team',options=[{'label':i, 'value':i} for i in team_list],value=team_list[0],style=admin_text_style)],style={}),
                                    html.Div([dcc.ConfirmDialogProvider(html.Button('Remove User',style=admin_user_button_style),id='remove_user_submit',message='Are you sure you want to remove this user?')])
                                    ],style=admin_col_style)  
                          ],style={}),
                html.Div(style=admin_divider_style),
                html.Div([html.Div([html.Div([html.B('Add New Skill',style={'fontSize':'24'})]), 
                                    html.Div([html.B('Skill Name :',style={'fontSize':'16'})]),
                                    html.Div([dcc.Input(id='new_skill', value='', type='text',style=admin_text_style)]),
                                    html.Div([dcc.ConfirmDialogProvider(html.Button('Add New Skill',style=admin_skill_button_style),id='new_skill_submit',message='Are you sure you wish to add this new skill?')])
                                    ],style=admin_col_style),
                          html.Div([html.Div([html.B('Remove Skill',style={'fontSize':'24'})]),
                                    html.Div([html.B('Skill :',style={'fontSize':'16'})]),
                                    html.Div([dcc.Dropdown(id='remove_skill_skill',options=[{'label':i, 'value':i} for i in skill_list],value=skill_list[0],style=admin_text_style)],style={}),
                                    html.Div([dcc.ConfirmDialogProvider(html.Button('Remove Skill',style=admin_user_button_style),id='remove_skill_submit',message='Are you sure you wish to remove this skill?')])
                                    ],style=admin_col_style)  
                          ],style={}),
                html.Div(),
                ]

### ADMIN PORTAL TAB ### This callback updates the user list when the team dropdown is changed ###    
@app.callback(
    Output('remove_user_user', 'options'),
    [Input('remove_user_team', 'value')])
def update_admin_users(value):
    people = dynamo_query(table=table, category='people') 
    return [{'label':i['name'], 'value':i['name']} for i in people['Items'] if i['team'] == value]
 
### ADMIN PORTAL TAB ### This callback adds new users to the database
@app.callback(Output('new_user_hidden','children'),
              [Input('new_user_submit','submit_n_clicks')],
              [State('new_user','value'),State('new_user_team','value')])
def submit_new_user(n_clicks,new_user,new_user_team):
    if n_clicks > 0:
        item = {'category':'people','key':new_user,'name':new_user,'team':new_user_team,'department':'DARC'}
        table.put_item(Item=item)
        return None
    
### ADMIN PORTAL TAB ### This callback adds new skills to the database
@app.callback(Output('new_skill_hidden','children'),
              [Input('new_skill_submit','submit_n_clicks')],
              [State('new_skill','value')])
def submit_new_skill(n_clicks,new_skill):
    if n_clicks > 0:
        item = {'category':'skill','key':new_skill +'-DARC','skill':new_skill,'department':'DARC'}
        table.put_item(Item=item)
        
        return None

### ADMIN PORTAL TAB ### This callback removes users from the database
@app.callback(Output('remove_user_hidden','children'),
              [Input('remove_user_submit','submit_n_clicks')],
              [State('remove_user_user','value')])
def remove_user(n_clicks,remove_user):
    if n_clicks > 0:
        key = {'category':'people','key':remove_user}
        table.delete_item(Key=key)
        return None

### ADMIN PORTAL TAB ### This callback removes users from the database
@app.callback(Output('remove_skill_hidden','children'),
              [Input('remove_skill_submit','submit_n_clicks')],
              [State('remove_skill_skill','value')])
def remove_skill(n_clicks,remove_skill):
    if n_clicks > 0:
        key = {'category':'skill','key':remove_skill +'-DARC'}
        print(key)
        table.delete_item(Key=key)
        return None


if __name__ == "__main__":
    app.run_server(debug=True, port=8080)