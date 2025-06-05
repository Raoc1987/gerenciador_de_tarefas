def formatar_data(data_str):
    partes = data_str.split('-')
    return f"{partes[2]}/{partes[1]}/{partes[0]}"
