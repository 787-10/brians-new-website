#![feature(proc_macro_hygiene, decl_macro)]
#![allow(unused_attributes)]

#[macro_use] use rocket::*;
use rocket_contrib::serve::StaticFiles;
use rocket_contrib::helmet::SpaceHelmet;
use rocket_contrib::templates::Template;


mod routes;

pub fn rocket_builder() -> rocket::Rocket {
    rocket::ignite()
        .attach(SpaceHelmet::default())
        .attach(Template::fairing())
        .mount("/", routes![routes::index::index_fn])
        .mount("/blog", routes![routes::blog::read_fn, routes::blog::blogs_fn])
        .mount("/projects", routes![routes::projects::projects_fn])
        .mount("/skiing", routes![routes::skiing::skiing_fn])
        .mount("/flying", routes![routes::flying::flying_fn, routes::flying::commercial_fn, routes::flying::ga_fn])
        .mount("/ping", routes![routes::ping::ping_fn])
        .mount("/static", StaticFiles::from("static/"))
}

