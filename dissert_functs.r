library(cowplot) # for plot_grid function
library(segmented) # for piecewise regression
library(repr) # for customizing plot size

library(roxygen2) # for documentation
library(RSQLite) # for loading and saving sqlite tables
library(tidyverse) # general eda

conn <- dbConnect(RSQLite::SQLite(), "nih.db")
df <- dbGetQuery(conn, "SELECT * FROM bike_data")

options(repr.plot.width=10, repr.plot.height=4) # change size of ggplot figures

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
    p <- ggplot(data=data, aes(x=seconds, y=cadence)) + geom_point()
    q <- p + geom_vline(xintercept = xintercepts, linetype='dashed',color='red') + 
            labs(title = paste(part,"(before)"))
    # New
    r <- ggplot(data=new_data, aes(x=seconds, y=cadence)) + geom_point() + 
            labs(title=paste(part, "(after)"))
    
    print(plot_grid(q,r, ncol=2)) # plots both plots next to each other
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
    part <- data$id_sess[1]
    print(part)
    
    data = data[data$cadence > 0,]
    data = data[data$cadence < 150,]
    data$seconds = 1:nrow(data)
    # Model is required by `segmented`
    data.lm <- lm(cadence ~ seconds, data=data)
    data.seg <- segmented(
        data.lm,
        seg.Z = ~ seconds, # variable to cut on
        npsi = cut # number of estimated cuts
    )
    
    if (cut == 1){
        # then we need the rest of the data
        # find out whether the cut was done at the end or beginning of dataset
        loc <- round(data.seg$psi[,2][1])
        middle = max(data$seconds)/2
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
        loc2 <- round(data.seg$psi[,2][2])
        
        new_data <- data %>% slice(loc1:loc2)
    } else {
        print("Not currently supported :/")
        break
    }
    
    plotter(data, new_data, data.seg)
    
    return(new_data)
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
    df_cut <- seg(temp_df, cut) # send to data be segmented
    return(df_cut)
}

# this file was created in python. It is includes an integer for how many cuts are expected for each session.
cuts = read_csv('piecewise_cuts.csv')
cuts = cuts[cuts$num_cuts <= 2,] # the segmented function is not very accurate for more than 2 cuts

all_df = data.frame()

pdf("1_2_piecewise_plots.pdf", onefile = TRUE, height=3, width=7)
for (part in cuts$id_sess)
{
    new_df <- id_cut(part)
    all_df <- rbind(all_df, new_df)
}
dev.off()