use rocket::*;
use rocket_contrib::templates::Template;
use std::collections::HashMap;
use std::fs;
use walkdir::WalkDir;
use std::path::Path;
use std::fs::File;
use serde::Serialize;
use std::io::{
    self,
    BufRead,
};

fn read_first_lines(file_path: &str, num_lines: usize) -> io::Result<Vec<String>> {
    let file = File::open(file_path)?;
    let reader = io::BufReader::new(file);
    let lines: Vec<String> = reader.lines()
        .take(num_lines)
        .filter_map(|line| line.ok())
        .collect();
    Ok(lines)
}

fn extract_date_from_content(lines: &[String]) -> Option<String> {
    // Look for a line that starts with "Date:" in the first few lines
    for line in lines.iter().take(5) {
        let trimmed = line.trim();
        if trimmed.to_lowercase().starts_with("date:") {
            let date = trimmed[5..].trim().to_string();
            if !date.is_empty() {
                return Some(date);
            }
        }
    }
    None
}

fn extract_hidden_from_content(lines: &[String]) -> bool {
    for line in lines.iter().take(8) {
        let trimmed = line.trim();
        if trimmed.to_lowercase().starts_with("hidden:") {
            let val = trimmed[7..].trim().to_lowercase();
            return val == "true" || val == "yes";
        }
    }
    false
}

fn extract_preview_text(lines: &[String]) -> String {
    // Skip the title (first line with #), date field, and empty lines
    // Take the first non-empty paragraph as preview
    let mut preview = String::new();
    let mut skip_title = true;
    
    for line in lines {
        let trimmed = line.trim();
        
        // Skip title line
        if skip_title && trimmed.starts_with('#') {
            skip_title = false;
            continue;
        }
        
        // Skip date field
        if trimmed.to_lowercase().starts_with("date:") {
            continue;
        }

        // Skip hidden field
        if trimmed.to_lowercase().starts_with("hidden:") {
            continue;
        }
        
        // Skip empty lines and section headers
        if trimmed.is_empty() || trimmed.starts_with('#') {
            if !preview.is_empty() {
                break; // We found our preview, stop here
            }
            continue;
        }
        
        // Add to preview
        if !preview.is_empty() {
            preview.push(' ');
        }
        preview.push_str(trimmed);
        
        // Limit preview length
        if preview.len() > 200 {
            // Use char_indices to find a safe boundary
            let mut truncate_at = 200;
            for (idx, _) in preview.char_indices() {
                if idx > 200 {
                    break;
                }
                truncate_at = idx;
            }
            
            preview.truncate(truncate_at);
            
            // Find last space to avoid cutting mid-word
            if let Some(last_space) = preview.rfind(' ') {
                preview.truncate(last_space);
            }
            preview.push_str("...");
            break;
        }
    }
    
    preview
}

fn extract_date_from_filename(filename: &str) -> Option<String> {
    // Try to extract year from filename (e.g., "2021-year-in-review.md")
    if filename.starts_with(char::is_numeric) {
        if let Some(year_end) = filename.find('-') {
            let year = &filename[..year_end];
            if year.len() == 4 {
                return Some(year.to_string());
            }
        }
    }
    None
}


fn get_file_paths(dir_path: &Path) -> Vec<String> {
    let mut file_paths = Vec::new();

    for entry in WalkDir::new(dir_path).into_iter().filter_map(|e| e.ok()) {
        let path = entry.path();
        if path.is_file() {
            if let Some(file_path) = path.to_str() {
                file_paths.push(file_path.to_string());
            }
        }
    }

    file_paths
}


#[derive(Serialize)]
struct Preview {
    order: usize,
    title: String,
    preview: String,
    link: String,
    date: String,
}


#[get("/")]
pub fn blogs_fn() -> Template {
    let mut context = HashMap::new();
    let mut stories = Vec::<Preview>::new();
    
    for path in get_file_paths(Path::new("blogs")).iter() {
        let mut story = Preview {
            order: 0, // Will be set after sorting
            title: "".to_string(),
            preview: "".to_string(),
            link: path.replace("blogs/", "blog/read/").replace(".md", ""),
            date: "".to_string(),
        };
        
        match read_first_lines(&path, 15) {
            Ok(lines) => {
                if extract_hidden_from_content(&lines) {
                    continue;
                }
                if let Some(first_line) = lines.first() {
                    story.title = first_line.replace("# ", "");
                }
                story.date = extract_date_from_content(&lines).unwrap_or_else(|| {
                    // Fallback to filename-based date extraction
                    if let Some(filename) = Path::new(&path).file_name() {
                        if let Some(filename_str) = filename.to_str() {
                            return extract_date_from_filename(filename_str).unwrap_or_default();
                        }
                    }
                    String::new()
                });
                story.preview = extract_preview_text(&lines);
            }
            Err(err) => {
                eprintln!("Error reading the file: {:?}", err);
            }
        }
        stories.push(story);
    }
    
    // Sort stories by date (most recent first)
    // Dates should be in YYYY-MM-DD format for proper string sorting
    stories.sort_by(|a, b| b.date.cmp(&a.date));
    
    // Update order numbers after sorting
    for (i, story) in stories.iter_mut().enumerate() {
        story.order = i + 1;
    }

    context.insert("posts", stories);
    Template::render("blog_list", &context)
}

#[get("/read/<title>")]
pub fn read_fn(title:String) -> Template {
    let mut context = HashMap::new();
    let mut url:String = "".to_string();
    let escaped_title = url_escape::encode_component_to_string(title, &mut url);
    println!("{}", escaped_title);
    let load_result = fs::read_to_string(format!("blogs/{}.md", escaped_title));
    let markdown_result = match load_result {
        Ok(markdown) => markdown,
        Err(_e) => format!("## 404: Could not find post\nCouldn't find post titled {}.", url)
    };
    let cleaned: String = markdown_result
        .lines()
        .filter(|line| !line.trim().to_lowercase().starts_with("hidden:"))
        .collect::<Vec<_>>()
        .join("\n");
    let mut options = markdown::Options::gfm();
    options.compile.allow_dangerous_html = true;
    let html = markdown::to_html_with_options(&cleaned, &options).unwrap();
    context.insert("raw_post", html);
    Template::render("blog", &context)
}
