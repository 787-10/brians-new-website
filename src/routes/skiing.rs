use rocket::*;
use rocket_contrib::templates::Template;
use std::collections::HashMap;

#[get("/")]
pub fn skiing_fn() -> Template {
    let mut context = HashMap::new();
    context.insert("context", "string");
    Template::render("skiing", &context)
}
