use rocket::*;
use rocket_contrib::templates::Template;
use std::collections::HashMap;

#[get("/")]
pub fn flying_fn() -> Template {
    let mut context = HashMap::new();
    context.insert("context", "string");
    Template::render("flying", &context)
}

#[get("/commercial")]
pub fn commercial_fn() -> Template {
    let mut context = HashMap::new();
    context.insert("context", "string");
    Template::render("commercial", &context)
}

#[get("/ga")]
pub fn ga_fn() -> Template {
    let mut context = HashMap::new();
    context.insert("context", "string");
    Template::render("ga", &context)
}
