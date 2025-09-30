#########################################
#                                       #
#   R E U S A B L E   M A K E F I L E   #
#                                       #
#########################################

######################
# Tunable parameters #
######################

#
# OBJS_DIR: Temporary directory where compiled objects will be placed.
#
OBJS_DIR := obj/

#
# PROG_DIR: Where program sources are found. One executable will be built for each source file.
#
PROG_DIR := progs/

#
# LIBS_DIR: Where library modules are. One object file will be built for each source file.
#
LIBS_DIR := libraries/

###########################################################
# You should not need to change anything below this line. #
###########################################################

#
# PROG_SRCS: All the source files of the programs.
#
PROG_SRCS := $(wildcard $(PROG_DIR)*.cpp)

#
# LIBS_SRCS: All the source files of the library.
#
LIBS_SRCS := $(wildcard $(LIBS_DIR)*.cpp)

#
# LIBS_HDRS: All the header files of the library.
#
LIBS_HDRS := $(wildcard $(LIBS_DIR)*.h)

#
# PROGRAMS: The names of all the executable files to build.
#
# This line replaces the folder name and drops the file extension, while keeping the file name.
#
PROGRAMS  := $(PROG_SRCS:$(PROG_DIR)%.cpp=%)

#
# LIBRARIES: The names of all the object (*.o) files of the filesystem library.
#
# This line substitutes the folder name and the file extension, while keeping the file name.
#
LIBS_OBJS := $(LIBS_SRCS:$(LIBS_DIR)%.cpp=$(OBJS_DIR)%.o)

#
# CC: Which C compiler to use.
#
CC        := g++

#
# CFLAGS: The parameters to pass to the compiler.
#
CFLAGS    := -O2 -Wall -Wpedantic -Wextra -Wstrict-aliasing -Wwrite-strings -Wshadow
CFLAGS    += -Wundef -Wno-unused-parameter -Wno-format-security
#CFLAGS    += -DNDEBUG

#
# LDFLAGS: The parameters to pass to the linker.
#
LDFLAGS   := -lpthread -ltbb

###########################
# Magic spells cheatsheet #
###########################

#
# $@: the target filename.
#
# $<: the first prerequisite filename.
#
# $^: the filenames of all the prerequisites, separated by spaces, discard duplicates.
#

####################
# Rule definitions #
####################

#
# This rule defines the default target. If no target is specified, it will be run.
#
# It has all the program executables as prerequisites, so it will try to build them.
#
all: $(PROGRAMS)
	printf "\nBuilt $(PROGRAMS)\n"

#
# This rule defines how to build an executable for each program.
#
# Its first prerequisite is the source code file for the program to build.
#
# The other prerequisites are the library objects, as they are needed to do the linking step.
#
# The recipe builds the program's source code, and then links it with the library objects.
#
%: $(PROG_DIR)%.cpp $(LIBS_OBJS)
	printf "    LINK  $(notdir $@)\n"
	$(CC) -o $@ $< $(LIBS_OBJS) $(CFLAGS) $(LDFLAGS)

#
# This rule defines how to compile each module of the library.
#
# Its first prerequisite is the source code file for the module to build.
#
# The second prerequisite is the output directory. It is created with its own rule.
#
# The other prerequisites are the headers. This will trigger a rebuild if they are changed.
#
# The recipe builds the library's source code, and places it in the temporary object directory.
#
$(OBJS_DIR)%.o: $(LIBS_DIR)%.cpp mkoutdir $(LIBS_HDRS)
	printf "    CC    $(notdir $@)\n"
	$(CC) -c -o $@ $< $(CFLAGS)

#
# This rule defines how to make the temporary object directory, where all object files will go.
#
mkoutdir:
	mkdir -p $(OBJS_DIR)

#
# This rule defines how to remove all build artifacts. It can be invoked like this: make clean
#
# It removes the temporary object directory as well as the executable programs.
#
clean:
	rm -rf $(OBJS_DIR)
	rm -f  $(PROGRAMS)

#
# This rule tells make to not echo any commands in the recipes. Otherwise, it results in spam.
#
.SILENT:

#
# This rule tells make that these targets are not actual files, so as to avoid mistakes.
#
.PHONY: all clean mkoutdir
