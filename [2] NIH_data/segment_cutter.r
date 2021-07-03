#!/usr/bin/env Rscript

db_name <- 'data/nih_scripts.db'        # name of db file containing bike_data and num_cuts
bike_table <- 'bike_data'        # name of table in db that has the formatted bike data
cut_table <- 'num_cuts'          # name of table in db that has number of cuts per dataset

plot_me <- TRUE                  # if TRUE will output a PDF with before after plots
pdf_name <- "dana_main_sess.pdf" # name of pdf output
save_table <- FALSE               # if TRUE will save table as "main_sessions" to the given sqlite database

#### PREREQS ####
# - Raw bikedata reorganized with raw_processing.py
# - SQLite database containing at least the following two tables
# - bike_data
#    Dataframe containing reorganized bike outputs with at least the following columns
#    - id_sess:     str,   participant id and session/day separated by '_'
#    - elapsed_sec: int,   seconds since the session began
#    - cadence:     float, cadence as given by the dynamic bike
# - num_cuts
#    Dataframe containing the suspected number of cuts for each id/session 
#    combination with the following columns
#    - id_sess:  str, participant id and session/day separated by '_'
#    - num_cuts: int, number of anticipated cuts. Currently only supports 1 or 2 cuts. 
#                     0s are ignored (assumed to be flag for review), 3s print out an error 
#                     (segmented regression not very accurate) but the script will continue.
##################

## library(roxygen2) # for documentation
library(RSQLite) # for loading and saving sqlite tables
library(tidyverse) # general eda
library(lubridate) # datetime management
library(segmented) # for piecewise regression

library(cowplot) # for plot_grid function
library(repr) # for customizing plot size

options(repr.plot.width=10, repr.plot.height=4) # change size of ggplot figures

## LOAD DATA
conn <- dbConnect(RSQLite::SQLite(), db_name)
df <- dbReadTable(conn=conn, name=bike_table)

# this file was created in python. It includes an integer for how many cuts are expected for each session.
cuts = dbReadTable(conn = conn, name = cut_table)
#cuts = cuts[cuts$num_cuts <= 2,] # the segmented function is not very accurate for more than 2 cuts
cuts = cuts[cuts$num_cuts > 0,] # a 0 indicates manual review needed

#' Segment Plotter
#' Uses old and new datasets, plus the returned estimates from `segmented` to create Before/After plots
#' 
#' @param data Original dataframe
#' @param new_data Dataframe without the unwanted segments
#' @param data.seg Returned segment key points from the `segmented` function
#' @export
plotter <- function(data, new_data, data.seg){
    xintercepts <- data.seg$psi[,2]
    # Old with Plan
    p <- ggplot(data=data, aes(x=elapsed_sec, y=cadence)) + geom_point()
    q <- p + geom_vline(xintercept = xintercepts, linetype='dashed',color='red') + 
        labs(title = paste(part,"(before)"))
    # New
    r <- ggplot(data=new_data, aes(x=elapsed_sec, y=cadence)) + geom_point() + 
        labs(title=paste(part, "(after)"))
    
    print(plot_grid(q,r, ncol=2)) # plots both plots next to each other
}


#' ID Cutter
#' Isolates a participants data from a larger df
#'
#' @param part String indicating the participant
#' @param cut Dataframe of id:num_cuts
#' @return New dataframe that excludes unwanted segments
#' @export
id_cut <- function(part, cut){
    temp_df <- df[df$id_sess == part,] # isolate participant from session
    cut <- cuts[cuts$id_sess ==part,]['num_cuts'] # and in the cuts df
    
    clean_temp_df <- cleaner(temp_df) # take out outliers from warmup/cooldown if they exist, otherwise return dataframe
    df_cut <- seg(clean_temp_df, cut) # send data to be segmented

    sane <- sanity(df_cut$elapsed_sec)
    
    if(sane==TRUE){
        df_cut$sane = TRUE
    } else {
        df_cut$sane = FALSE
    }
    
    return(df_cut)
}

#' Sanity Checker
#' Checks whether the given column is sequential
sanity <- function(vector){
    diff_vector <- diff(vector)
    result <- sum(diff_vector != 1)
    if(result > 0){
        return(FALSE) # failed
    } else {
        return(TRUE) # passed
    }
}

#' Cleaner
#' Removes outrageous outliers from warmups/cooldowns to avoid them biasing the `seg` function
#' 
#' @param data Dataset with id_sess, elapsed_sec, cadence columns
#' @return data Same dataset but with removed outliers
#' @export
cleaner <- function(data){
    part <- data$id_sess[1]
    
    if(nrow(data)>2000){
        less_z <- sum((data$cadence < -50) & (data$elapsed_sec < 600)) + sum((data$cadence < -50) & (data$elapsed_sec > 1500))
        more_h <- sum((data$cadence > 150) & (data$elapsed_sec < 600)) + sum((data$cadence > 150) & (data$elapsed_sec > 1500))        
    }else{
        less_z <- sum((data$cadence < -50) & (data$elapsed_sec < 600)) + sum((data$cadence < -50) & (data$elapsed_sec > 1500))
        more_h <- sum((data$cadence > 150) & (data$elapsed_sec < 600)) + sum((data$cadence > 150) & (data$elapsed_sec > nrow(data)-300)) 
    }
    new_data <- data.frame()
    # skipping for now
#    if ((less_z + more_h) > 0){
    # cut dataset apart
    temp_df.warm <- data[(data$elapsed_sec < 600),]
    temp_df.rest <- data[(data$elapsed_sec > 600) & (data$elapsed_sec < 2000),]
    temp_df.cool <- data[(data$elapsed_sec > 2000),]

    if (less_z > 0){
        # extract outlier
        temp_df.warm = temp_df.warm[temp_df.warm$cadence > -50,]
        temp_df.cool = temp_df.cool[temp_df.cool$cadence > -50,]

        print(paste("WARNING: ", part, " has cadence in the warmup or cooldown that is < -50! It has been cut out."))
    }
    if (more_h > 0){
        # extract outlier
        temp_df.warm = temp_df.warm[temp_df.warm$cadence < 150,]
        temp_df.cool = temp_df.cool[temp_df.cool$cadence < 150,]

        print(paste("WARNING: ", part, " has cadence in the warmup or cooldown that is > 150! It has been cut out."))

    if (sum(df$cadence < -50) > 0){
        temp_df.rest = temp_df.rest[temp_df.rest$cadence > -50,]
        print(paste("WARNING: ", part, " has cadence in the main session that is < -50! It has been cut out."))
    } 
    if (sum(df$cadence > 150) > 0){
        temp_df.rest = temp_df.rest[temp_df.rest$cadence < 150,]
        print(paste("WARNING: ", part, " has cadence in the main session that is > 150! It has been cut out."))
    } 
    } else {
        return(data)
    }
    # paste dataset back together
    new_data <- rbind(new_data, temp_df.warm, temp_df.rest, temp_df.cool)
    new_data <- new_data[order(new_data$elapsed_sec, decreasing=FALSE),]
    return(new_data)


}

#' Segmenter
#' Uses piecewise regression to cut datasets apart. Only 1 or 2 cuts supported.
#' 
#' @param data Dataset with at least cadence column
#' @param cut Integer indiciating the number of cuts required for the dataset
#' @return A new dataset with 1 or 2 segments extracted
#' @examples
#' seg(data, 2)
#' @export
seg <- function(data, cut) {
    # Model is required by `segmented`
    if(dim(data)[1] == 0){
        return(FALSE)
    }
    data.lm <- lm(cadence ~ elapsed_sec, data=data)
    data.seg <- segmented(
        data.lm,
        seg.Z = ~ elapsed_sec, # variable to cut on
        npsi = cut # number of estimated cuts
    )
    
    if (cut == 1){
        # then we need the rest of the data
        # find out whether the cut was done at the end or beginning of dataset
        loc <- round(data.seg$psi[,2][1])
        middle = max(data$elapsed_sec)/2
        if (loc < middle){
            # if less than middle, then beginning is cut
            new_data <- data %>% slice(loc:nrow(data))
        }
        else{
            # if more than middle, then end is cut
            new_data <- data %>% slice(1:loc)
        }

    } else if (cut == 2){
        loc1 <- round(data.seg$psi[,2][1])
        loc2 <- round(data.seg$psi[,2][2]) # keeps leaving the tailend of datasets
        new_data <- data %>% slice(loc1:loc2)
    } else {
        print("Not currently supported :/")
        break
    }
    if(plot_me){
        plotter(data, new_data, data.seg)
    }
    return(new_data)
}

clean_df <- data.frame()
sane_v <- c()
part_v <- c()

pdf(pdf_name, onefile = TRUE, height=3, width=7)
for (part in unique(cuts$id_sess)) # run function only on the sane datasets
{
    check <- tryCatch(
        # try to do all this
        {
        df_cut <- id_cut(part)
        clean_df <- rbind(clean_df, df_cut)
        sane_v <- append(sane_v, df_cut$sane[1])
        part_v <- append(part_v, part)
        print(paste(part, 'sequential =', df_cut$sane[1])) # TRUE if sane, FALSE if insane
        },
    warning = function(war)
        # If a warning occurs, print it
        {
            print(paste("WARNING", part, ": ", war))
        },
    error = function(err)
        # If an error occurs, print it
        {
            print(paste("ERROR: ", part, ": ", err))
        }, 
    finally = function(f)
        # Otherwise just print it
        {
            print(paste("e: ", part, ": ", e))
        }) 
}
dev.off()

if(save_table){
    # save table if user wants to save it
    dbWriteTable(conn=conn, name="main_sessions")
}