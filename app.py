import pandas as pd
from flask import Flask, request, render_template
import io

app = Flask(__name__)

@app.route('/')
def home():
    clientes_df = pd.read_csv('clientes.csv')
    clientes = clientes_df['Clientes'].tolist()
    clientes.insert(0, '')  # Adiciona uma string vazia no começo da lista
    clientes.insert(1, 'TODOS')  # Adiciona uma opção para todos os clientes
    return render_template('upload.html', clientes=clientes)


@app.route('/upload', methods=['POST'])
def upload():
    # Obtém o cliente selecionado
    cliente = request.form['cliente']

    # Verifica se foi selecionado um cliente
    if not cliente:
        return 'Selecione um cliente'
    # Verifica se foi enviado um arquivo CSV
    if 'file' not in request.files:
        return 'Nenhum arquivo selecionado'
    try:
        # Lê o arquivo CSV
        csv_file = request.files['file']
        csv_data = csv_file.read().decode('utf-8')
        # Cria um dataframe com os dados do CSV
        df = pd.read_csv(io.StringIO(csv_data))
    except pd.errors.EmptyDataError:
        return 'Arquivo vazio ou sem colunas para processar'
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

    # Passa a lista de dados e o cliente selecionado para o template
    return render_template('results.html', results=filtered_results, cliente=cliente)

if __name__ == '__main__':
    app.run(debug=True)