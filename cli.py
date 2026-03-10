import os
import sys
import json
import requests
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

BASE_URL = "http://localhost:8000"
SESSION_FILE = ".astryx_session.json"

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def save_session(session_id, name):
    with open(SESSION_FILE, "w") as f:
        json.dump({"session_id": session_id, "name": name}, f)

def generate_chart():
    console.print(Panel.fit("[bold magenta]Astryx — Chart Generation[/bold magenta]"))
    
    name = Prompt.ask("Enter your name")
    gender = Prompt.ask("Enter your gender", choices=["Male", "Female", "Other"])
    dob = Prompt.ask("Enter your date of birth (YYYY-MM-DD)", default="1990-03-21")
    tob = Prompt.ask("Enter your time of birth (HH:MM) 24-hour format", default="10:30")
    city = Prompt.ask("Enter your city of birth (e.g., Mumbai, India)")
    tz_offset = float(Prompt.ask("Enter your timezone offset from GMT (e.g., 5.5 for IST)", default="5.5"))

    payload = {
        "name": name,
        "gender": gender,
        "dob": dob,
        "tob": tob,
        "city": city,
        "tz_offset": tz_offset
    }

    with console.status("[bold green]Computing your cosmic blueprint...[/bold green]"):
        try:
            response = requests.post(f"{BASE_URL}/api/chart", json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error computing chart:[/bold red] {e}")
            if 'response' in locals() and response is not None:
                console.print(f"[red]Server Response:[/red] {response.text}")
            return

    chart_data = data["chart"]
    
    save_session(data["session_id"], name)

    console.print(f"\n[bold cyan]Ascendant (Lagna):[/bold cyan] {chart_data['ascendant']['sign']} ({chart_data['ascendant']['degree']}°)")
    
    table = Table(title="Planetary Placements")
    table.add_column("Planet", style="magenta")
    table.add_column("Sign", style="green")
    table.add_column("House", justify="right", style="yellow")
    table.add_column("Nakshatra", style="cyan")
    table.add_column("Longitude", justify="right")

    for planet, info in chart_data["planets"].items():
        table.add_row(
            planet,
            info["sign"],
            str(info["house"]),
            info["nakshatra"],
            f"{info['longitude']}°"
        )
    
    console.print(table)
    
    if chart_data.get("doshas"):
        console.print(f"[bold red]Detected Doshas:[/bold red] {', '.join(chart_data['doshas'])}")
    
    if "dasha" in chart_data:
        dasha = chart_data["dasha"]
        mah = dasha.get("mahadasha", {})
        ant = dasha.get("antardasha", {})
        console.print(f"[bold yellow]Current Mahadasha:[/bold yellow] {mah.get('planet', 'N/A')} (Ends: {mah.get('end', 'N/A')})")
        console.print(f"[bold yellow]Current Antardasha:[/bold yellow] {ant.get('planet', 'N/A')} (Ends: {ant.get('end', 'N/A')})")

    console.print(f"\n[bold green]Chart Generated Successfully![/bold green]")
    console.print(f"Session saved for [bold]{name}[/bold]. You can now chat!\n")

    if data.get("suggested_questions"):
        console.print("[dim]Suggested Questions:[/dim]")
        for q in data["suggested_questions"]:
            console.print(f"- {q}")
    print()

def start_chat():
    session = load_session()
    if not session:
        console.print("[bold red]No active session found![/bold red] Please generate a chart first.")
        print()
        return

    session_id = session["session_id"]
    name = session.get("name", "Astral Voyager")

    console.print(Panel.fit(f"[bold blue]Astryx Chat[/bold blue]\nConsulting chart for: [bold]{name}[/bold]"))
    console.print("Type [bold red]'exit'[/bold red] to return to main menu.\n")

    while True:
        question = Prompt.ask("[bold cyan]You[/bold cyan]")
        if question.lower() in ["exit", "quit", "menu", "back", "q"]:
            console.print("[dim]Returning to main menu...[/dim]\n")
            break

        payload = {
            "session_id": session_id,
            "message": question
        }

        with console.status("[bold green]Astryx is consulting the stars...[/bold green]"):
            try:
                response = requests.post(f"{BASE_URL}/api/chat", json=payload, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                answer = data.get("answer", "I could not find an answer.")
                console.print("\n[bold magenta]Astryx:[/bold magenta]")
                console.print(Markdown(answer))
                print()
            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Error communicating with Astryx:[/bold red] {e}")
                if 'response' in locals() and response is not None:
                     console.print(f"[red]Server Response:[/red] {response.text}")

def main():
    console.print(Panel.fit("[bold blue]Welcome to Astryx[/bold blue]\nYour Vedic Astrology Companion"))
    
    while True:
        session = load_session()
        active_str = f" [green](Active chart: {session['name']})[/green]" if session else ""
        
        console.print(f"[bold]Main Menu[/bold]{active_str}")
        console.print("1. Generate New Chart")
        console.print("2. Chat with Astryx")
        console.print("3. Exit")
        
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"])
        
        if choice == "1":
            print()
            generate_chart()
        elif choice == "2":
            print()
            start_chat()
        elif choice == "3":
            console.print("Goodbye.")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nGoodbye.")
        sys.exit(0)
