from nycparking.queries.dashboard_queries import top_violations


def main():
    df = top_violations()
    print(df.head())


if __name__ == "__main__":
    main()
