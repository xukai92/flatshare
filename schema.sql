drop table if exists flats;
create table flats (
  flat_id integer primary key autoincrement,
  flat_name text not null,
  password text not null,
  country text not null DEFAULT 'uk'
);

drop table if exists members;
create table members (
  member_id integer primary key autoincrement,
  member_name text not null,
  flat_id integer,
  FOREIGN KEY (flat_id) REFERENCES flats(flat_id)
);

drop table if exists bills;
create table bills (
  bill_id integer primary key autoincrement,
  content text not null,
  amount double not null,
  member_id integer,
  created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (member_id) REFERENCES flats(member_id)
);
