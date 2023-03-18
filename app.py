import pandas as pd
from flask import Flask, render_template, request, make_response, current_app, g, send_file
from unidecode import unidecode
import os.path
import sqlite3
import io
import re
import unicodedata
import csv

app = Flask(__name__)
app.config['DATABASE'] = 'database.db'


def get_db():
    if 'db' not in g:
        database_file = current_app.config['DATABASE']
        if not os.path.exists(database_file):
            # Create the file if it doesn't exist yet
            open(database_file, 'w').close()
        # Cria uma nova conexão com o banco de dados
        g.db = sqlite3.connect(
            database_file, detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Define para que as linhas do banco de dados possam ser acessadas como dicionários
        g.db.row_factory = sqlite3.Row
        g.db.commit()

    return g.db


@app.route('/')
def home():
    clientes_df = pd.read_csv('clientes.csv')
    clientes = clientes_df['Clientes'].tolist()
    clientes.insert(0, '')  # Adiciona uma string vazia no começo da lista
    clientes.insert(1, 'TODOS')  # Adiciona uma opção para todos os clientes
    return render_template('upload.html', clientes=clientes)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Obtém o cliente selecionado
        cliente = request.form['cliente']
        # Verifica se foi selecionado um cliente
        if not cliente:
            return 'Selecione um cliente'
        # Verifica se foi enviado um arquivo CSV
        if 'file' not in request.files:
            return 'Nenhum arquivo selecionado'
        try:
            f = request.files['file']
            if not f:
                return "Arquivo não encontrado"

            stream = io.StringIO(f.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream, quoting=csv.QUOTE_NONE)
            header = next(csv_input)

            # Criando um dataframe com os dados lidos do CSV
            df = pd.DataFrame(csv_input, columns=header)
            df = df.apply(lambda x: x.str.replace('"', ''))
        except pd.errors.EmptyDataError:
            return 'ERRO-203: Arquivo vazio ou sem colunas para processar'
        # Filtra os dados pelo cliente selecionado na coluna "serviço"
        if cliente == 'TODOS':
            filtered_df = df
        else:
            filtered_df = df[df['Serviço'] == cliente]
        # Verifica se a caixa de seleção foi marcada
        if request.form.get('excluir_cve'):
            filtered_df = filtered_df[~filtered_df.apply(
                lambda row: row.astype(str).str.contains(r'\bCVE').any(), axis=1)]
        if request.form.get('excluir_dh'):
            filtered_df = filtered_df[~filtered_df.apply(
                lambda row: row.astype(str).str.contains(r'\bPing the remote host').any(), axis=1)]
        if request.form.get('only_cve'):
            filtered_df = filtered_df[filtered_df.apply(
                lambda row: row.astype(str).str.contains(r'\bCVE').any(), axis=1)]
        if request.form.get('only_dh'):
            filtered_df = filtered_df[filtered_df.apply(
                lambda row: row.astype(str).str.contains(r'\bPing the remote host').any(), axis=1)]
        # Ordena o dataframe pelo valor da coluna "Serviço" em ordem alfabética crescente
        filtered_df = filtered_df.sort_values(by=['Serviço'])
        # Converte o dataframe filtrado para uma lista de listas
        filtered_results = [filtered_df.columns.tolist()] + \
            filtered_df.values.tolist()
        # Converte os valores das colunas com acentos e cedilha para caracteres ASCII
        filtered_results = [[unidecode(str(cell)) for cell in row]
                            for row in filtered_results]

        # Armazena a lista de resultados filtrados no banco de dados
        db = get_db()
        cursor = db.cursor()

        # Criando a tabela no banco de dados
        columns = []
        for col in df.columns:
            count = df.columns.tolist().count(col)
            col = unicodedata.normalize('NFKD', col).encode(
                'ASCII', 'ignore').decode('ASCII')
            # substitui caracteres especiais por underscore
            col = re.sub(r'[^a-zA-Z0-9_]', '_', col)
            if count > 1:
                col = col + '_' + str(count)
            columns.append(col)

        table_name = 'results'
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join([f'{col} text' for col in columns])})")
        db.commit()

        # Inserindo os dados na tabela
        values_list = []
        columns_str = ', '.join(columns)
        for row in df.iterrows():
            values = [str(val).replace('"', "'") for val in row[1].values]
            if len(values) != len(columns):
                raise ValueError(
                    f"Number of columns ({len(columns)}) does not match number of values ({len(values)})")
            values_list.append(tuple(values))

        insert_query = f'INSERT INTO results ({columns_str}) VALUES ({",".join(["?" for _ in range(len(columns))])})'
        cursor.executemany(insert_query, values_list)
        db.commit()

        # Passa a lista de dados e o cliente selecionado para o template
        return render_template('results.html', results=filtered_results, cliente=cliente)


@app.route('/download')
def download():
    # Get the filtered results from the database
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT data FROM filtered_results')
    result = cursor.fetchone()
    if result is None:
        return 'Nenhum resultado filtrado encontrado'
    # Convert the string representation of the list of lists back to a list of lists
    filtered_results = eval(result[0])
    # Create a Pandas DataFrame from the filtered results
    df = pd.DataFrame(filtered_results[1:], columns=filtered_results[0])
    # Create an in-memory Excel file from the DataFrame
    excel_file = io.BytesIO()
    with pd.ExcelWriter(excel_file, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    excel_file.seek(0)
    # set the file name for download
    filename = "my_excel_file.xlsx"
    # send the in-memory Excel file to the user as an attachment
    return send_file(excel_file, as_attachment=True, download_name=filename)


if __name__ == '__main__':
    app.run(debug=True)
