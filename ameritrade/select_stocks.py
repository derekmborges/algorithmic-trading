from google.cloud import bigquery
import pandas as pd

def select_stocks(event, context):
    client = bigquery.Client()

    # Load all the data in the table
    sql_hist = """
        SELECT date, symbol, closePrice, lowPrice, highPrice, totalVolume, volatility
        FROM `splendid-cirrus-302501.stock_data.daily_quote_data`
    """
    df = client.query(sql_hist).to_dataframe()

    # Sort by date ascending
    df = df.sort_values(by='date').reset_index(drop=True)

    # Calculate day change percent
    dayChange = []
    for i in df.index:
        try:
            high = df['highPrice'][i]
            low = df['lowPrice'][i]
            if low and low > 0:
                dayChange.append(round(((high - low) / low) * 100, 2))
            else:
                dayChange.append(0)
        except KeyError:
            dayChange.append(0)
    df['dayChange'] = dayChange


    # Calculate averages
    symbols = df['symbol'].unique()
    symbol_data = {}
    for symbol in symbols:
        symbol_df = df[df['symbol'] == symbol]
        symbol_df = symbol_df.set_index('date')
        symbol_df['averageDayChange50'] = symbol_df['dayChange'].ewm(span=50).mean()
        symbol_df['averageVolume50'] = symbol_df['totalVolume'].ewm(span=50).mean()
        symbol_df['averageVolume10'] = symbol_df['totalVolume'].ewm(span=10).mean()
        symbol_data[symbol] = symbol_df
    
    # Rebuild DataFrame with most recent values for each stock
    recent_df = pd.DataFrame(columns=df.columns)
    for symbol in symbols:
        i = len(symbol_data[symbol].index) - 1
        recent_df = recent_df.append(symbol_data[symbol].iloc[i])
    
    # Filter stocks by high volatility criteria
    filtered_df = recent_df.query(
        'averageDayChange50>4.5 & averageVolume50>4000000 & averageVolume10>4000000 & closePrice>=5'
    )

    # Sort descending by averageDayChange50
    sorted_df = filtered_df.sort_values('averageDayChange50', ascending=False)

    # Grab top 5 stocks
    selected_stocks = sorted_df[:5]
    selected_stocks['date'] = selected_stocks.index.values
    print(selected_stocks)

    dataset_id = 'stock_data'
    table_id = 'selected_stocks'

    dataset_ref = client.dataset(dataset_id)
    table_ref = dataset_ref.table(table_id)

    job_config = bigquery.LoadJobConfig()
    job_config.autodetect = True
    job_config.write_disposition = 'WRITE_TRUNCATE' # Always replace table data
    job = client.load_table_from_dataframe(selected_stocks, table_ref, job_config=job_config)
    job.result()
    print('Success')

select_stocks(None, None)
