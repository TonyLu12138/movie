"""Development entry point; production servers can import app:app."""
import os

from movie_app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8000")), debug=False)
