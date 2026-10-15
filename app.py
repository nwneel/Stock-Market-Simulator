# Flet Stock App with live Data & Charts - Alpha Advantage API
import flet as ft
import flet_charts as fch
from stock_data import StockDataError, get_stock_data, search_stock_symbol

# Main Flet Interface -> Function based
def main(page: ft.Page):
    # App Settings
    page.title = "Stock Market Simulator"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO
    page.window.width = 1000
    page.window.height = 700
    
    #State Variables - Widgets in our App
    stock_symbol = ft.Ref[ft.TextField]()
    chart_container = ft.Ref[ft.Container]()
    price_info = ft.Ref[ft.Container]()
    price_text_below = ft.Ref[ft.Container]()
    error_messages = ft.Ref[ft.Container]()
    time_range_dropdown = ft.Ref[ft.Dropdown]()
    
    # Time range for the stock
    def get_days_for_range(range_name):
        ranges = {
            "1 week": 7,
            "1 month": 30,
            "3 months": 90,
            "1 year": 365,
            "5 years": 1825,
            "Max": 18262,
        }
        return ranges.get(range_name, 30)
    
    def get_range_label(range_name):
        return range_name
    
    # Fetch the stock with our API
    def fetch_stock_data(e):
        query = (stock_symbol.current.value or "").strip()
        symbol = query.upper()
        company_name = None
        time_range = time_range_dropdown.current.value or "1 month"
        days = get_days_for_range(time_range)  # 365
        
        if not query:
            error_messages.current.content = ft.Text("Please enter a company name or stock symbol", color=ft.Colors.RED, size=14)
            error_messages.current.visible = True
            price_info.current.visible = False
            price_text_below.current.visible = False
            chart_container.current.visible = False
            page.update()
            return
        
        error_messages.current.visible = False
        error_messages.current.content = ft.Text("", color=ft.Colors.RED, size=14 )
        
        # Load the stock.. waiting
        loading_text = ft.Text("Loading Stock Data...", size=16, color=ft.Colors.BLUE)
        chart_container.current.content = loading_text
        chart_container.current.visible = True
        page.update()
        
        #Fetch the API data
        try: 
            if any(not (character.isalnum() or character in ".^-") for character in query):
                symbol, company_name = search_stock_symbol(query)
                time_series = get_stock_data(symbol)
            else:
                try:
                    time_series = get_stock_data(symbol)
                except StockDataError as error:
                    message = str(error)
                    if not (
                        message.startswith("No daily stock data was returned")
                        or message.startswith("Alpha Vantage: Invalid API call")
                    ):
                        raise
                    symbol, company_name = search_stock_symbol(query)
                    time_series = get_stock_data(symbol)

            dates = sorted(time_series.keys(), reverse=True)[:days]
            dates.reverse()
            
            # Prep the charts
            opens, highs, lows, closes = [], [], [], []
            
            for date in dates:
                day_data = time_series[date]
                open_price = float(day_data["1. open"])
                high_price = float(day_data["2. high"])
                low_price = float(day_data["3. low"])
                close_price = float(day_data["4. close"])
                
                opens.append(open_price)
                highs.append(high_price)
                lows.append(low_price)
                closes.append(close_price)
            
            latest_date = max(time_series)
            latest_data = time_series[latest_date]
            
            #Time to make some charts in Flet!
            #Update price info
            price_info.current.content = ft.Column([
                ft.Text(
                    f"Stock: {symbol}" + (f" - {company_name}" if company_name else ""),
                    size=24,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLUE_700,
                ),
                ft.Text(f"Date: {latest_date}", size=14,weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                ft.Divider(height=1),
                
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"Open", size=12, color=ft.Colors.GREY_600),
                            ft.Text(f"{float(latest_data['1. open']):.2f}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                        ],spacing=5),
                        padding=15,
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=10,
                        expand=True
                    ),
                     ft.Container(
                        content=ft.Column([
                            ft.Text(f"High", size=12, color=ft.Colors.GREY_600),
                            ft.Text(f"{float(latest_data['2. high']):.2f}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_900),
                        ],spacing=5),
                        padding=15,
                        bgcolor=ft.Colors.GREEN_50,
                        border_radius=10,
                        expand=True
                    ),
                     ft.Container(
                        content=ft.Column([
                            ft.Text(f"Low", size=12, color=ft.Colors.GREY_600),
                            ft.Text(f"{float(latest_data['3. low']):.2f}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_900),
                        ],spacing=5),
                        padding=15,
                        bgcolor=ft.Colors.RED_50,
                        border_radius=10,
                        expand=True
                    ),
                     ft.Container(
                        content=ft.Column([
                            ft.Text(f"Close", size=12, color=ft.Colors.GREY_600),
                            ft.Text(f"{float(latest_data['4. close']):.2f}", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_900),
                        ],spacing=5),
                        padding=15,
                        bgcolor=ft.Colors.PURPLE_50,
                        border_radius=10,
                        expand=True
                    ),
                ], spacing=10)
            ])
            price_info.current.visible = True
            # Container -> Columns and Rows
            
            # Make the Charts
            chart = fch.LineChart(
                data_series=[
                    fch.LineChartData(
                        points=[
                            fch.LineChartDataPoint(
                                i,
                                closes[i],
                                tooltip=f"{dates[i]}\nClose: ${closes[i]:.2f}",
                            )
                            for i in range(len(closes))
                        ],
                        stroke_width=3,
                        color=ft.Colors.ORANGE,
                        below_line_bgcolor=ft.Colors.ORANGE_100,
                    ),
                ],
                border=ft.Border(
                    bottom=ft.BorderSide(4, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    left=ft.BorderSide(4, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    top=ft.BorderSide(4, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                    right=ft.BorderSide(4, ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE)),
                ),
                left_axis=fch.ChartAxis(
                    label_size=50,
                ),
                bottom_axis=fch.ChartAxis(
                    label_size=40,
                ),
                min_y=min(closes) * 0.95,
                max_y=max(closes) * 1.05,
                min_x=0,
                max_x=max(1, len(closes)-1),
                interactive=True,
                height=300,
            )
            
            chart_container.current.content = ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"Closing Prices - {get_range_label(time_range)} ({symbol})",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Daily prices; up to 100 recent trading sessions are available. "
                        "Hover over the chart to see the date and closing price.",
                        size=12,
                        color=ft.Colors.GREY_700,
                    ),
                    chart,
                ],spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=20,
                border=ft.Border.all(2, ft.Colors.GREY_300),
                border_radius=10,
            )
            chart_container.current.visible = True
            
            #Add Price Text below the chart
            price_text_below.current.content = ft.Text(
                f"Open: ${float(latest_data['1. open']):.2f} | "
                f"High: ${float(latest_data['2. high']):.2f} | "
                f"Low: ${float(latest_data['3. low']):.2f} | "
                f"Close: ${float(latest_data['4. close']):.2f} | ",
                size=16,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER
            )
            price_text_below.current.visible = True
            
        except StockDataError as error:
            error_messages.current.content = ft.Text(str(error), color=ft.Colors.RED, size=14)
            error_messages.current.visible = True
            price_info.current.visible = False
            price_text_below.current.visible = False
            chart_container.current.visible = False
            
        page.update()
        
    # UI Layout
    page.add(
        ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("Stock Market Simulator"),
                    ft.Text("Enter a stock symbol or company name to view the chart")
                ], spacing=5, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.only(bottom=20),
                alignment=ft.Alignment.CENTER
            ),
            # Search Bar and Date Picker
            ft.Container(
                content=ft.Row([
                    ft.TextField(
                        ref=stock_symbol,
                        label="Stock Symbol or Company Name",
                        hint_text="AAPL, AMZN, GOOGL, Microsoft",
                        width=300,
                        autofocus=True,
                        on_submit=fetch_stock_data,
                    ),
                    ft.Dropdown(
                        ref=time_range_dropdown,
                        width=150,
                        options=[
                            ft.dropdown.Option("1 week"),
                            ft.dropdown.Option("1 month"),
                            ft.dropdown.Option("3 months"),
                            ft.dropdown.Option("1 year"),
                            ft.dropdown.Option("5 years"),
                            ft.dropdown.Option("Max"),
                        ],
                        value="1 month"
                    ),
                    ft.Button(
                        "Get Stock Data",
                        icon=ft.Icons.SEARCH,
                        on_click=fetch_stock_data,
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.BLUE_700,
                        ),
                    ),
                ], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                alignment=ft.Alignment.CENTER
            ),
            ft.Container(
                ref=error_messages,
                content=ft.Text(""),
                padding=10,
                visible=False
            ),
            ft.Container(
                ref=price_info,
                padding=10,
                visible=False
            ),
            ft.Container(
                ref=chart_container,
                padding=10,
                visible=False
            ),
            ft.Container(
                ref=price_text_below,
                padding=10,
                visible=False
            ),
        ], spacing=15, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    )


if __name__ == "__main__":
    ft.run(main)