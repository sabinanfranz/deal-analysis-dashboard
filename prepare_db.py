# prepare_db.py
import pandas as pd, sqlite3, pathlib

BASE = pathlib.Path(__file__).parent
FILES = {
    "all_deal": BASE / "all deal.txt",
    "won_deal": BASE / "won deal.txt",
    "retention": BASE / "retention corp.txt",
}

def load_to_db(db_path="deals.db"):
    con = sqlite3.connect(db_path)
    for name, path in FILES.items():
        df = pd.read_csv(path, sep="\t")
        df.to_sql(name, con, if_exists="replace", index=False)
    con.commit()
    con.close()

if __name__ == "__main__":
    load_to_db()
