import psycopg2
conn = psycopg2.connect("postgresql://neondb_owner:npg_QbHpRZW8of3C@ep-hidden-wind-a1q0el7s-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='loto6_results' ORDER BY ordinal_position")
print([r[0] for r in cur.fetchall()])
conn.close()
