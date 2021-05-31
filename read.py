import os
import re
import json 
import unidecode
import requests as req
from bs4 import BeautifulSoup
import pandas as pd
from slugify import slugify
import codecs


def save_file(filename, content):
    file = codecs.open(filename, "w", "utf-8")
    file.write(content)
    file.close()

def get_validacao(txt):
    txt = txt.replace(']]', '').strip()
    if 'Validação:' in txt:
        x = txt.split('Validação:')
        return x[1]
    return '-'

def get_valores_validos(txt):
    txt = txt.replace(']]\\', '').strip()
    if 'Valores válidos:' in txt:
        x = txt.split('Valores válidos:')
        if 'Validação:' in x[1]:
            a = x[1].split('Validação:')
            return a[0]
        return x[1]
    return '{}'


def get_valores_validos_json(txt):
    import json
    txt = txt.replace('\\', '').replace('\n', '').split('[[')
    dictionary = {}
    del txt[0]
    for a in txt:
        key = a.split(']]')
        key = key[0].strip()
        value = a.replace(']]', '')
        if key:
            dictionary[key] = value.strip()
    return dictionary


def tratando_descricao(descricao):
    descricao = descricao.replace('Ver: ', '').replace(' > ', ' ')
    return descricao.split(' ')


def get_descricao(txt):
    return txt.replace(']]', '').replace('\\', '\n').replace('\n ', '\n').replace('[[', '').replace('  ', ' ').replace('  ', ' ').strip()


def recursive(df, i, index_list, i_max): 
    df_pai = df.loc[i]
    df_child_e = df.loc[(df['grupo-pai'] == df_pai['grupo-campo']) & (df['elem'] == 'E') & (df.index < i_max)]
    for ce in df_child_e.index.tolist(): 
        index_list.append(ce)
    df_child_g = df.loc[(df['grupo-pai'] == df_pai['grupo-campo']) & (df['elem'].isin(['CG', 'G'])) & (df.index < i_max)]
    for cg in df_child_g.index.tolist(): 
        index_list.append(cg)
    for index, child in df_child_g.iterrows():
        index_list = recursive(df, index, index_list, i_max)
    return index_list


def get_child(df, pai, campo, i_max):
    index_list = []
    df_pai = df.loc[(df['grupo-pai'] == pai) & (df['grupo-campo'] == campo)]
    df_child_e = df.loc[(df['grupo-pai'] == campo) & (df['elem'] == 'E') & (df.index < i_max)]
    for ce in df_child_e.index.tolist(): 
        index_list.append(ce)
    df_child_g = df.loc[(df['grupo-pai'] == campo) & (df['elem'].isin(['CG', 'G'])) & (df.index < i_max)]
    for cg in df_child_g.index.tolist(): 
        index_list.append(cg)
    for index, child in df_child_g.iterrows():
        index_list = recursive(df, index, index_list, i_max)
    return df.loc[df.index.isin(index_list)]


def read_esocial_tabelas(path, url):

    r = req.get(url)
    r.encoding = r.apparent_encoding
    html_content = r.text

    html_content = html_content.replace('<strong>', "[[")
    html_content = html_content.replace('<br />', "\\")
    html_content = html_content.replace('</strong>', "]]")

    soup = BeautifulSoup(html_content, "html.parser")
    li = str(soup.find_all("ul", {"class":"sumario"})[0])
    table_names = BeautifulSoup(li, "html.parser").find_all("li")
    table_names = [tn.get_text() for tn in table_names]
    tables = soup.find_all("table", {"class":"table is-fullwidth is-bordered completo"})
    
    for n in range(len(table_names)):
        table_name = table_names[n]
        header = 0
        table = pd.read_html(str(tables[n]), header=header)[0]
        table.columns = [slugify(c) or 'esocial_id' for c in table.columns]

        table['validacao'] = table.apply(lambda x: get_validacao(x['descricao']), axis=1)
        table['valores-validos'] = table.apply(lambda x: get_valores_validos(x['descricao']), axis=1)
        table['valores-validos'] = table.apply(lambda x: get_valores_validos_json(x['valores-validos']), axis=1)
        table['descricao'] = table.apply(lambda x: get_descricao(x['descricao']), axis=1)

        indexes = table.index[table['grupo-campo'].isnull()].tolist()
        if indexes:
            indexes_mod = [0] + indexes + [max(indexes)+1]
            dfs_list = [table.iloc[indexes_mod[n]:indexes_mod[n+1]] for n in range(len(indexes_mod)-1)]

            new_df = dfs_list[0]

            del dfs_list[0]

            for n in range(len(dfs_list)):
                df_ = dfs_list[n]
                filter = tratando_descricao(df_['descricao'].tolist()[0])
                pai = filter[0]
                campo = filter[1]
                i_max = indexes[n]
                new_df = new_df.append(get_child(table, pai, campo, i_max))
                new_df = new_df.append(df_)
        
        else:
            new_df = table
        
        new_df = new_df.reset_index()
        new_df['index'] = new_df.index + 1

        table = new_df[new_df['elem'].notna()]
         
        dictionary = {
            'name': table_name, 
            'content': table.to_dict(orient='records')}

        if not os.path.exists(path):
            os.makedirs(path)
                
        json_object = json.dumps(dictionary, indent = 4, ensure_ascii=False)
        filename = os.path.join(path, '{}.json'.format(slugify(table_name)))
        save_file(filename, json_object)


if __name__ == "__main__":
    eventos = [
        ['v_S_01_00_00', 
         'https://www.gov.br/esocial/pt-br/documentacao-tecnica/leiautes-esocial-nt-01-2021-html/index.html/'],
    ]
    for evt in eventos:
        read_esocial_tabelas(evt[0], evt[1])


